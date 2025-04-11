# Pick Me Randomly

A Streamlit application for managing and voting on nail polish collections.

## Setup

1. Clone the repository
2. Create a virtual environment: `python -m venv venv`
3. Activate the virtual environment:
   - Windows: `venv\Scripts\activate`
   - Unix/MacOS: `source venv/bin/activate`
4. Install dependencies: `pip install -r requirements.txt`
5. Copy `.env.template` to `.env` and fill in your database credentials
6. Initialize the database: `python scripts/init_db.py`
7. Run the application: `streamlit run app.py`

## Docker Deployment

1. Build the Docker image: `docker build -t pick-me-randomly .`
2. Run the container: `docker run -p 8501:8501 --env-file .env pick-me-randomly`

## Fly.io Deployment

1. Install the Fly.io CLI
2. Login to Fly.io: `fly auth login`
3. Launch the app: `fly launch`
4. Set up the Postgres database: `fly postgres create`
5. Attach the database: `fly postgres attach <db-name>`
6. Deploy the app: `fly deploy`

## Database Schema

The application uses a Postgres database with the following schema:

- `votes` table: Stores voting data for nail polishes
  - `id`: Primary key
  - `number`: Polish number
  - `brand`: Brand name
  - `shade_name`: Shade name
  - `finish`: Finish type
  - `collection`: Collection name
  - `winner_number`: Winning polish number
  - `winner_brand`: Winning polish brand
  - `winner_shade_name`: Winning polish shade name
  - `winner_finish`: Winning polish finish
  - `winner_collection`: Winning polish collection
  - `created_at`: Timestamp of vote
