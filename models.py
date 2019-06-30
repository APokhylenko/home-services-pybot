from _operator import or_
from datetime import datetime, timedelta

from sqlalchemy import Column, Integer, String, Boolean, exists, DateTime, func, desc, create_engine, ForeignKey, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker

# Create an engine which the Session will use for connections.
from settings import DB_URL, RENTER_USERNAME

engine = create_engine(DB_URL)

# Create session
Session = sessionmaker(bind=engine)
session = Session()

# Create a base for the models to build upon.
Base = declarative_base()


class User(Base):
    """User will be created when /start command used."""
    __tablename__ = "users"

    user_id = Column(Integer, primary_key=True)
    first_name = Column(String, nullable=False)
    last_name = Column(String)
    username = Column(String)
    counters = relationship("Counters", backref='users')
    is_renter = Column(Boolean, default=False)
    is_muted = Column(Boolean, default=False)

    def __init__(self, user, is_admin=False, is_muted=False):
        self.user_id = user.id
        self.first_name = user.first_name
        self.last_name = user.last_name
        self.username = user.username
        self.is_admin = is_admin
        self.is_muted = is_muted

    def exists(self):
        return session.query(exists().where(
            User.user_id == self.user_id)).scalar()

    def commit(self):
        if self.username == RENTER_USERNAME:
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

    def calculate_total_price(self, flat_price, exchange_rate, user_id):
        """Calculate total price for the flat with bills."""
        electricity, gas, water = Counters.get_last_values_difference(user_id)

        electricity_before_100 = electricity
        electricity_after_100 = 0

        if electricity >= 100:
            electricity_before_100 = 100
            electricity_after_100 = electricity - 100
        flat = flat_price * exchange_rate
        electricity = electricity_before_100 * self.electricity_before_100 + electricity_after_100 * self.\
            electricity_after_100
        gas *= self.gas
        water *= self.water
        total = flat + electricity + gas + water + self.sdpt + self.garbage_removal
        return total, electricity, gas, water

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

        if counters_last and counters_previous:
            electricity = counters_last.electricity - counters_previous.electricity
            gas = counters_last.gas - counters_previous.gas
            water = counters_last.water - counters_previous.water
        return electricity, gas, water

    @staticmethod
    def get_last_values_difference(user_id):
        """Returns last indications."""
        counters = Counters.get_last_and_previous_user_counters(user_id)
        return Counters.calculate_counters_difference(*counters)

    @staticmethod
    def get_current_month_counters_data(user_id):
        """Returns counters data for current month."""
        ten_days_before = datetime.now() - timedelta(days=10)
        return session.query(Counters).filter(
            Counters.created >= ten_days_before,
            user_id == user_id).first()

    @staticmethod
    def load_previous_counters_data(user):
        """Try to load previous counters data."""
        try:
            from data.counters_data import DATA
            for d in DATA:
                counters = Counters(**d)
                counters.user_id = user.user_id
                counters.commit()
        except ImportError:
            print('No data found.')

    def commit(self):
        session.add(self)
        session.commit()


Base.metadata.create_all(engine)
