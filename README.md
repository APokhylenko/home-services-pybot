# home-services-pybot
Telegram bot for managing counters data and bills for the communal services between renter and home owner


  pip install -r requirements.py
  cp .env.example .env
  set db path, email, tg, etc
  cd src/data
  cp counters_data.py.example counters_data.py 
  alembic upgrade head
  python main.py
