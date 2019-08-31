from datetime import datetime

from sqlalchemy import Column, Integer, String, Boolean, exists, DateTime, func, desc, create_engine, ForeignKey, Float, \
    UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker

# Create an engine which the Session will use for connections.
from helpers import get_heating_bill
from settings import DB_URL, RENTER_USERNAME

engine = create_engine(DB_URL, connect_args={'check_same_thread': False})

# Create session
Session = sessionmaker(bind=engine)
session = Session()

# Create a base for the models to build upon.
Base = declarative_base()


class User(Base):
    """User will be created when /start command used."""
    __tablename__ = "users"

    user_id = Column(Integer, primary_key=True)
    chat_id = Column(Integer)
    first_name = Column(String, nullable=False)
    last_name = Column(String)
    username = Column(String)
    counters = relationship("Counters", backref='users')
    is_renter = Column(Boolean, default=False)
    is_muted = Column(Boolean, default=False)

    def __init__(self, user, is_muted=False, chat_id=None):
        self.user_id = user.id
        self.first_name = user.first_name
        self.last_name = user.last_name
        self.username = user.username
        self.is_muted = is_muted
        self.chat_id = chat_id

    def exists(self):
        return session.query(exists().where(
            User.user_id == self.user_id)).scalar()

    @staticmethod
    def get_user_by_username(username):
        return session.query(User).filter(User.username == username).first()

    def commit(self):
        if self.username == RENTER_USERNAME:
            Counters.load_previous_counters_data(self)
            self.is_renter = True
        session.add(self)
        session.commit()

    def __repr__(self):
        return "<User (user_id='%i', first_name='%s', username='%s')>" % (
            self.user_id, self.first_name, self.username
        )


class Rates(Base):
    """Services rates."""

    __tablename__ = "rates"

    id = Column(Integer, primary_key=True)
    water = Column(Float)
    gas = Column(Float)
    electricity_before_100 = Column(Float)
    electricity_after_100 = Column(Float)
    garbage_removal = Column(Float)
    sdpt = Column(Float)
    flat = Column(Float)
    flat_summer = Column(Float)

    def __init__(self, water=23.6, gas=7.5, electricity_before_100=0.9, electricity_after_100=1.68,
                 garbage_removal=17.11, sdpt=148.73, flat=200, flat_summer=300):
        self.water = water
        self.gas = gas
        self.electricity_before_100 = electricity_before_100
        self.electricity_after_100 = electricity_after_100
        self.garbage_removal = garbage_removal
        self.sdpt = sdpt
        self.flat = flat
        self.flat_summer = flat_summer

    @staticmethod
    def create_default_rates():
        """Creates instance with default rates."""
        default_rates = Rates()
        default_rates.commit()
        return default_rates

    @staticmethod
    def get_default_rates():
        """Returns instance with default rates."""
        default_rates = session.query(Rates).get(1)

        if not default_rates:
            default_rates = Rates.create_default_rates()
        return default_rates

    def get_flat_price(self):
        """Returns flat price depending on season."""
        now = datetime.now()
        current_month = now.strftime('%m')
        summer_months = ['06', '07', '08', '09']

        if current_month in summer_months:
            price = self.flat_summer
        else:
            price = self.flat
        return price

    @staticmethod
    def diff_month(d1, d2):
        return (d1.year - d2.year) * 12 + d1.month - d2.month

    @staticmethod
    def calculate_electricity(electricity, electricity_before_100_rate, electricity_after_100_rate):
        """0-100 electricity has different price than 100+."""
        electricity_before_100 = electricity
        electricity_after_100 = 0

        if electricity >= 100:
            electricity_before_100 = 100
            electricity_after_100 = electricity - 100
        electricity = electricity_before_100 * electricity_before_100_rate + electricity_after_100 * \
                      electricity_after_100_rate
        return electricity

    @staticmethod
    def calculate_flat_bill(flat_price, exchange_rate):
        """Check when last payment was done. Get diff, then multiply diff * flat price * exchange rate."""
        last_payment_date = FlatPayment.get_last_payment_date()
        months_after_last_payment = Rates.diff_month(datetime.now(), last_payment_date) or 1
        flat = flat_price * exchange_rate * abs(months_after_last_payment)
        return flat

    @staticmethod
    def calculate_sdpt_garbage_removal(last_counters_date, sdpt_rate, garbage_removal_rate):
        """Check date of the last counters data. Get diff, then multiply diff * rates.
        By default we assume that 1 month passed."""
        months_after_last_payment = 1
        if last_counters_date:
            months_after_last_payment = Rates.diff_month(datetime.now(), last_counters_date) or 1
        sdpt = months_after_last_payment * sdpt_rate
        garbage_removal = months_after_last_payment * garbage_removal_rate
        return sdpt, garbage_removal

    def calculate_total_price(self, flat_price, exchange_rate, user_id):
        """Calculate total price for the flat with bills for the water/gas/energy..."""
        electricity_difference, gas_difference, water_difference, last_counters_created_date = \
            Counters.get_last_values_difference(user_id)
        bills = dict()
        bills['electricity'] = self.calculate_electricity(electricity_difference,
                                                          self.electricity_before_100,
                                                          self.electricity_after_100)
        bills['flat'] = self.calculate_flat_bill(flat_price, exchange_rate)

        bills['gas'] = gas_difference * self.gas
        bills['water'] = water_difference * self.water
        bills['sdpt'], bills['garbage_removal'] = self.calculate_sdpt_garbage_removal(last_counters_created_date,
                                                                                      self.sdpt, self.garbage_removal)
        bills['heating'] = get_heating_bill()
        bills['total'] = bills['flat'] + bills['electricity'] + bills['gas'] + bills['water'] + bills['sdpt'] + \
                         bills['garbage_removal'] + bills['heating']
        bills['last_counters_created_date'] = last_counters_created_date

        return bills

    def commit(self):
        session.add(self)
        session.commit()


class FlatPayment(Base):
    """Save month and year of the payment status."""

    __tablename__ = "flat_payments"

    id = Column(Integer, primary_key=True)
    month_number = Column(Integer, default=datetime.now().month)
    year = Column(Integer, default=datetime.now().year)
    is_paid = Column(Boolean, default=False)
    __table_args__ = (UniqueConstraint('year', 'month_number', name='_year_month_uc'),)

    def __repr__(self):
        return f"Paid {self.is_paid} {self.month_number}.{self.year}"

    @staticmethod
    def generate_flat_payments():
        """Try to load previous payments data."""
        try:
            from data.counters_data import LAST_PAYMENT_DATA as LPD
            paid_months = session.query(FlatPayment).filter_by(year=LPD['year']).count()
            if paid_months >= LPD['month_number']:
                return
            months = range(1, LPD['month_number'] + 1)
            flat_payments = []
            for m in months:
                data = {'month_number': m, 'year': LPD['year'], 'is_paid': LPD['is_paid']}
                flat_payments.append(FlatPayment(**data))

            session.bulk_save_objects(flat_payments)
            session.commit()
        except ImportError:
            print('Error. No data found.')

    @staticmethod
    def get_this_year_payments():
        return session.query(FlatPayment).filter_by(year=datetime.now().year, is_paid=True)

    @staticmethod
    def mark_as_paid_or_unpaid(month_number):
        """Set is_paid to opposite."""
        month_data = {'month_number': month_number, 'year': datetime.now().year}
        instance = session.query(FlatPayment).filter_by(**month_data).first()
        if instance:
            instance.is_paid = not instance.is_paid
            FlatPayment.commit(instance)
        else:
            month_data['is_paid'] = True
            instance = FlatPayment(**month_data)
            FlatPayment.commit(instance)
        pass

    @staticmethod
    def get_last_payment_date():
        """Return number of the month when last payment was done."""
        last_payment = session.query(FlatPayment).filter_by(is_paid=True). \
            order_by(FlatPayment.year.desc(), FlatPayment.month_number.desc()).first()
        if not last_payment:
            raise ValueError
        return datetime(year=last_payment.year, month=last_payment.month_number, day=1)

    def commit(self):
        session.add(self)
        session.commit()


class Counters(Base):
    """Counters data goes here."""

    __tablename__ = "counters"

    id = Column(Integer, primary_key=True)
    electricity = Column(Integer)
    gas = Column(Integer)
    water = Column(Integer)
    user_id = Column(Integer, ForeignKey('users.user_id'))
    gas_counter_photo_url = Column(String)
    created = Column(DateTime(timezone=True), server_default=func.now())
    updated = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self):
        return f"Counters {self.updated} from {self.user_id}"

    @staticmethod
    def get_last_and_previous_user_counters(user_id):
        """Returns last counters and previous counters data for specific user."""
        counters = session.query(Counters).filter_by(user_id=user_id).order_by(Counters.updated.desc()).limit(2).all()
        counters_last, counters_previous = None, None

        try:
            counters_last = counters[0]
            counters_previous = counters[1]
        except IndexError:
            pass
        return counters_last, counters_previous

    @staticmethod
    def get_last_user_counters(user_id):
        """Returns last counters data for specific user."""
        return session.query(Counters).filter_by(user_id=user_id).order_by(desc(Counters.updated)).first()

    @staticmethod
    def calculate_counters_difference(*counters):
        """Calculate difference between old and new counters data."""
        counters_last, counters_previous = counters
        electricity = gas = water = 0
        counters_last_created = counters_last.created if counters_last else None

        if counters_last and counters_previous:
            electricity = counters_last.electricity - counters_previous.electricity
            gas = counters_last.gas - counters_previous.gas
            water = counters_last.water - counters_previous.water
        return electricity, gas, water, counters_last_created

    @staticmethod
    def get_last_values_difference(user_id):
        """Returns last indications."""
        counters = Counters.get_last_and_previous_user_counters(user_id)
        return Counters.calculate_counters_difference(*counters)

    @staticmethod
    def get_current_month_counters_data(user_id):
        """Returns counters data for current month."""
        first_day_of_month = datetime.today().replace(day=1)
        return session.query(Counters).filter(
            Counters.created >= first_day_of_month,
            user_id == user_id).first()

    @staticmethod
    def load_previous_counters_data(user):
        """Try to load previous counters data."""
        try:
            from data.counters_data import DATA
            counters_list = []
            for d in DATA:
                counters = Counters(**d)
                counters.user_id = user.user_id
                counters_list.append(counters)
            session.bulk_save_objects(counters_list)
            session.commit()
        except ImportError:
            print('No data found.')

    def commit(self):
        session.add(self)
        session.commit()


Base.metadata.create_all(engine)
