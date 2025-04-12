import streamlit as st
import pandas as pd
import random
from tqdm import tqdm
import os
from datetime import datetime
import time
import logging
import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# Page configuration
st.set_page_config(
    page_title="Pick Me Randomly",
    page_icon="💅",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Constants
COLLECTION_FILE = 'NPS.xlsx'
SELECTIONS_FILE = 'NPS_Selections.xlsx'
COLLECTION_SHEET = 'Original_Swatches'
HISTORY_SHEET = 'Sheet1'
SELECTIONS_SHEET = 'Selections'

# Check if we're running in a container
IS_CONTAINER = os.getenv('IS_CONTAINER', 'false').lower() == 'true'

# Get database configuration from environment variables
DATABASE_URL = os.getenv('DATABASE_URL')
DATABASE_HOST = os.getenv('DATABASE_HOST')
DATABASE_PORT = os.getenv('DATABASE_PORT')
DATABASE_USER = os.getenv('DATABASE_USER')
DATABASE_PASSWORD = os.getenv('DATABASE_PASSWORD')
DATABASE_NAME = os.getenv('DATABASE_NAME')

# Create a connection pool
connection_pool = None

def init_connection_pool():
    global connection_pool
    if connection_pool is None:
        try:
            logging.debug("=== Initializing connection pool ===")
            logging.debug(f"Using DATABASE_URL for connection")
            
            connection_pool = psycopg2.pool.SimpleConnectionPool(
                1,  # min connections
                10,  # max connections
                dsn=DATABASE_URL
            )
            logging.debug("Connection pool initialized successfully")
            
            # Test the connection
            with connection_pool.getconn() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT version();")
                    version = cursor.fetchone()
                    logging.debug(f"PostgreSQL version: {version}")
                    
                    # Check if votes table exists
                    cursor.execute("""
                        SELECT EXISTS (
                            SELECT FROM information_schema.tables 
                            WHERE table_name = 'votes'
                        );
                    """)
                    table_exists = cursor.fetchone()[0]
                    logging.debug(f"Votes table exists: {table_exists}")
                    
                    if table_exists:
                        # Get current count of votes
                        cursor.execute("SELECT COUNT(*) FROM votes")
                        count = cursor.fetchone()[0]
                        logging.debug(f"Current number of votes in database: {count}")
                        
        except Exception as e:
            logging.error(f"Error initializing connection pool: {str(e)}")
            raise

@contextmanager
def get_db_connection():
    """Get a database connection from the pool"""
    if connection_pool is None:
        init_connection_pool()
    
    conn = connection_pool.getconn()
    try:
        logging.debug("Getting connection from pool")
        yield conn
    except Exception as e:
        logging.error(f"Error getting connection: {str(e)}")
        raise
    finally:
        logging.debug("Returning connection to pool")
        connection_pool.putconn(conn)

def init_database():
    """Initialize the database and create necessary tables"""
    try:
        logging.debug("=== Starting database initialization ===")
        logging.debug(f"Using DATABASE_URL for initialization")
        
        # Initialize the connection pool if not already done
        if connection_pool is None:
            init_connection_pool()
        
        # Get a connection from the pool
        with get_db_connection() as conn:
            conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
            cursor = conn.cursor()
            
            # Create votes table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS votes (
                id SERIAL PRIMARY KEY,
                number TEXT,
                brand TEXT,
                shade_name TEXT,
                finish TEXT,
                collection TEXT,
                winner_number TEXT,
                winner_brand TEXT,
                winner_shade_name TEXT,
                winner_finish TEXT,
                winner_collection TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            ''')
            
            # Verify table creation
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'votes'
                );
            """)
            table_exists = cursor.fetchone()[0]
            logging.debug(f"Votes table exists: {table_exists}")
            
            if table_exists:
                # Get current count of votes
                cursor.execute("SELECT COUNT(*) FROM votes")
                count = cursor.fetchone()[0]
                logging.debug(f"Current number of votes in database: {count}")
            
            logging.debug("Database tables initialized successfully")
            cursor.close()
            conn.close()
        
    except Exception as e:
        logging.error(f"Error initializing database: {str(e)}")
        raise

@st.cache_data
def load_data():
    """Load and return the polish collection, history, and previous selections"""
    with st.spinner('Loading data...'):
        try:
            # Load the full collection
            collection_df = pd.read_excel(COLLECTION_FILE, sheet_name=COLLECTION_SHEET, engine='openpyxl')
        except Exception as e:
            logging.error(f"Error loading collection file: {str(e)}")
            # Create an empty DataFrame with required columns
            collection_df = pd.DataFrame(columns=['Number', 'Brand', 'Shade Name', 'Description', 'Finish', 'Notes'])
        
        # Ensure all necessary columns are present
        expected_columns = ['Number', 'Brand', 'Shade Name', 'Description', 'Finish', 'Notes']
        for col in expected_columns:
            if col not in collection_df.columns:
                collection_df[col] = ''
        # Replace all NaN values with empty strings
        collection_df = collection_df.fillna('')
        
        try:
            # Load history data
            history_df = pd.read_excel(COLLECTION_FILE, sheet_name=HISTORY_SHEET, engine='openpyxl', usecols='F:N')
            history_df.columns = ['Date', 'Number', 'Brand', 'Shade Name', 'Description', 'Finish', 'L', 'M', 'Notes']
            # Clean up the data
            history_df['Brand'] = history_df['Brand'].fillna('Unknown')
            history_df['Date'] = pd.to_datetime(history_df['Date'], errors='coerce')
            # Remove entries without dates
            history_df = history_df.dropna(subset=['Date'])
        except Exception as e:
            logging.error(f"Error loading history file: {str(e)}")
            # Create an empty DataFrame with required columns
            history_df = pd.DataFrame(columns=['Date', 'Number', 'Brand', 'Shade Name', 'Description', 'Finish', 'L', 'M', 'Notes'])
        
        # Replace all remaining NaN values with empty strings
        history_df = history_df.fillna('')
        
        try:
            # Load previous selections (just numbers)
            selections_df = pd.read_excel(SELECTIONS_FILE, sheet_name=SELECTIONS_SHEET, engine='openpyxl')
        except Exception as e:
            logging.error(f"Error loading selections file: {str(e)}")
            selections_df = pd.DataFrame(columns=['Number', 'Votes'])
        
        # Ensure we have the Number column
        if 'Number' not in selections_df.columns:
            selections_df = pd.DataFrame(columns=['Number', 'Votes'])
        if 'Votes' not in selections_df.columns:
            selections_df['Votes'] = 1
        # Replace all NaN values with empty strings
        selections_df = selections_df.fillna('')
            
        # Get the list of used numbers
        used_numbers = set(selections_df['Number'].unique())
        
        return collection_df, selections_df, used_numbers, history_df

def get_random_polishes(collection_df, used_numbers, count=5):
    """Get random polishes that haven't been selected before"""
    available_polishes = collection_df[~collection_df['Number'].isin(used_numbers)]
    
    if len(available_polishes) < count:
        return available_polishes
    
    random_indices = random.sample(list(available_polishes.index), count)
    return available_polishes.loc[random_indices]

def record_vote(selected_polish, polishes):
    """Record votes for all polishes in a round"""
    try:
        logging.debug("=== Starting record_vote function ===")
        logging.debug(f"Selected polish: {selected_polish}")
        logging.debug(f"All polishes in round: {polishes}")
        
        # Get database connection
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                # Get current count before insert
                cursor.execute('SELECT COUNT(*) FROM votes')
                before_count = cursor.fetchone()[0]
                logging.debug(f"Votes count before insert: {before_count}")
                
                for polish in polishes:
                    logging.debug(f"Processing vote for polish: {polish}")
                    
                    # Insert vote record
                    cursor.execute('''
                    INSERT INTO votes (
                        number, brand, shade_name, finish, collection,
                        winner_number, winner_brand, winner_shade_name, winner_finish, winner_collection
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ''', (
                        polish['Number'],
                        polish['Brand'],
                        polish['Shade Name'],
                        polish['Finish'],
                        polish.get('Collection', ''),
                        selected_polish['Number'],
                        selected_polish['Brand'],
                        selected_polish['Shade Name'],
                        selected_polish['Finish'],
                        selected_polish.get('Collection', '')
                    ))
                
                # Commit the transaction
                conn.commit()
                
                # Get count after insert
                cursor.execute('SELECT COUNT(*) FROM votes')
                after_count = cursor.fetchone()[0]
                logging.debug(f"Votes count after insert: {after_count}")
                logging.debug(f"Number of votes added: {after_count - before_count}")
                
    except Exception as e:
        logging.error(f"Error in record_vote: {str(e)}")
        raise

def calculate_statistics():
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Calculate most popular polishes
        cursor.execute('''
        SELECT winner_number, winner_brand, winner_shade_name, winner_finish, COUNT(*) as votes
        FROM votes
        GROUP BY winner_number, winner_brand, winner_shade_name, winner_finish
        ORDER BY votes DESC
        LIMIT 10
        ''')
        popular_polishes = cursor.fetchall()
        
        # Calculate brand statistics
        cursor.execute('''
        SELECT brand, COUNT(*) as appearances, 
               SUM(CASE WHEN number = winner_number THEN 1 ELSE 0 END) as wins
        FROM votes
        GROUP BY brand
        ''')
        brand_stats = cursor.fetchall()
        
        # Calculate finish statistics
        cursor.execute('''
        SELECT finish, COUNT(*) as appearances, 
               SUM(CASE WHEN number = winner_number THEN 1 ELSE 0 END) as wins
        FROM votes
        GROUP BY finish
        ''')
        finish_stats = cursor.fetchall()
        
    return popular_polishes, brand_stats, finish_stats

def display_statistics():
    popular_polishes, brand_stats, finish_stats = calculate_statistics()
    
    # Display most popular polishes
    st.write("### 🏆 Most Popular Polishes 🏆")
    popular_df = pd.DataFrame(popular_polishes, columns=['Number', 'Brand', 'Shade Name', 'Finish', 'Votes'])
    st.dataframe(
        popular_df[['Brand', 'Shade Name', 'Finish', 'Votes']],
        hide_index=True,
        use_container_width=True
    )
    
    # Display brand statistics
    st.write("### 📊 Brand Statistics 📊")
    brand_df = pd.DataFrame(brand_stats, columns=['Brand', 'Appearances', 'Wins'])
    brand_df['Win Percentage'] = (brand_df['Wins'] / brand_df['Appearances']) * 100
    st.dataframe(
        brand_df[['Brand', 'Appearances', 'Wins', 'Win Percentage']],
        hide_index=True,
        use_container_width=True
    )
    
    # Display finish statistics
    st.write("### 🎨 Finish Statistics 🎨")
    finish_df = pd.DataFrame(finish_stats, columns=['Finish', 'Appearances', 'Wins'])
    finish_df['Win Percentage'] = (finish_df['Wins'] / finish_df['Appearances']) * 100
    st.dataframe(
        finish_df[['Finish', 'Appearances', 'Wins', 'Win Percentage']],
        hide_index=True,
        use_container_width=True
    )
    
    # Add dark mode styling
    st.markdown("""
    <style>
    .stDataFrame {
        background-color: var(--background-color);
        color: var(--text-color);
    }
    .stDataFrame th {
        background-color: var(--secondary-background-color);
        color: var(--text-color);
    }
    .stDataFrame td {
        color: var(--text-color);
    }
    </style>
    """, unsafe_allow_html=True)

def cleanup_test_data():
    """Remove any test data from the database"""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    DELETE FROM votes 
                    WHERE number = 'TEST' 
                    AND brand = 'TEST' 
                    AND shade_name = 'TEST'
                """)
                deleted_count = cursor.rowcount
                conn.commit()
                if deleted_count > 0:
                    logging.debug(f"Cleaned up {deleted_count} test records")
    except Exception as e:
        logging.error(f"Error cleaning up test data: {str(e)}")

def verify_database():
    """Verify database connection and table structure"""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                # Check if table exists
                cursor.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = 'votes'
                    );
                """)
                table_exists = cursor.fetchone()[0]
                
                if not table_exists:
                    logging.error("Votes table does not exist")
                    return False
                
                # Clean up any existing test data
                cleanup_test_data()
                
                # Just check if we can read from the table
                cursor.execute("SELECT COUNT(*) FROM votes")
                count = cursor.fetchone()[0]
                logging.debug(f"Database contains {count} votes")
                
                return True
                    
    except Exception as e:
        logging.error(f"Database verification failed: {str(e)}")
        return False

def display_database():
    st.subheader("Database View")
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM votes")
        rows = cursor.fetchall()
        
        # Get column names from the cursor description
        columns = [desc[0] for desc in cursor.description]
        
        # Convert to DataFrame for display
        db_df = pd.DataFrame(rows, columns=columns)
        
        st.dataframe(db_df, hide_index=True, use_container_width=True)

def vote(selected_polish, all_polishes):
    """Handle the vote recording process"""
    try:
        logging.debug("=== Starting vote function ===")
        logging.debug(f"Selected polish: {selected_polish}")
        logging.debug(f"All polishes in round: {all_polishes}")
        
        # Record votes for all polishes in the round
        record_vote(selected_polish, all_polishes)
        
        # Show success message
        st.success("Vote recorded successfully!")
        
    except Exception as e:
        logging.error(f"Error in vote function: {str(e)}")
        st.error("Failed to record vote. Please try again.")

def main():
    # Initialize database and verify connection
    init_database()
    cleanup_test_data()  # Clean up any test data before starting
    if not verify_database():
        st.error("Database initialization failed. Please check the logs.")
        return
    
    st.title("💅 Pick Me Randomly")
    
    # Sidebar navigation
    page = st.sidebar.radio("Navigation", ["Vote", "History", "Statistics", "Database"])
    
    if page == "Vote":
        collection_df, _, used_numbers, _ = load_data()
        random_polishes = get_random_polishes(collection_df, used_numbers)
        
        st.subheader("Select Your Favorite Polish")
        st.write("Choose from these randomly selected polishes:")
        
        # Create columns for polish cards
        cols = st.columns(3)
        
        for i, polish in enumerate(random_polishes.to_dict('records')):
            with cols[i % 3]:
                with st.container():
                    # Only show Collection Info if Notes is not empty
                    collection_info = f"<p><strong>Collection Info:</strong> {polish['Notes']}</p>" if polish['Notes'] else ""
                    st.markdown(f"""
                    <div style='
                        padding: 20px; 
                        border-radius: 10px; 
                        background-color: var(--background-color);
                        border: 1px solid var(--border-color);
                        margin-bottom: 20px;
                        color: var(--text-color);
                    '>
                        <h3 style='color: var(--text-color);'>{polish['Brand']}</h3>
                        <p><strong style='color: var(--text-color);'>Shade:</strong> {polish['Shade Name']}</p>
                        <p><strong style='color: var(--text-color);'>Finish:</strong> {polish['Finish']}</p>
                        <p><strong style='color: var(--text-color);'>Description:</strong> {polish['Description']}</p>
                        {collection_info}
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # Make button key unique by including the index
                    if st.button("Select this polish", key=f"select_{polish['Number']}_{i}"):
                        logging.debug(f"Button clicked for polish {polish['Number']}")
                        logging.debug("Calling vote function")
                        vote(polish, random_polishes.to_dict('records'))
                        logging.debug("Vote recording completed")
                        st.success("Selection recorded! Refreshing...")
                        time.sleep(1)
                        st.rerun()
    
    elif page == "History":
        _, _, _, history_df = load_data()
        
        st.subheader("Kat's Personal Selection History")
        
        if not history_df.empty:
            # Add filters
            col1, col2 = st.columns(2)
            with col1:
                # Get unique brands, excluding 'Unknown' and sort them
                unique_brands = [brand for brand in sorted(history_df['Brand'].unique()) if brand != 'Unknown']
                brand_filter = st.multiselect(
                    "Filter by Brand",
                    options=unique_brands,
                    default=[]
                )
            with col2:
                date_filter = st.date_input(
                    "Filter by Date",
                    value=None
                )
            
            # Apply filters
            filtered_data = history_df
            if brand_filter:
                filtered_data = filtered_data[filtered_data['Brand'].isin(brand_filter)]
            if date_filter:
                filtered_data = filtered_data[filtered_data['Date'].dt.date == date_filter]
            
            # Display the filtered data
            st.dataframe(
                filtered_data[['Date', 'Brand', 'Shade Name', 'Description', 'Finish', 'Notes']],
                column_config={
                    "Date": st.column_config.DatetimeColumn(
                        "Date",
                        format="D MMM YYYY"
                    )
                },
                hide_index=True,
                use_container_width=True
            )
        else:
            st.info("No selection history available yet.")
    
    elif page == "Statistics":
        # Calculate and display basic statistics at the top
        st.write("### 🌟 Kat's Personal Collection and Usage Journey 🌟")
        st.write("brought to you by /r/WeGotPolishatHome")
        collection_df, _, _, history_df = load_data()
        total_polishes = len(collection_df)
        worn_polishes = history_df['Number'].nunique()
        percent_worn = (worn_polishes / total_polishes) * 100
        total_days = (history_df['Date'].max() - history_df['Date'].min()).days
        polishes_per_week = worn_polishes / (total_days / 7)
        weeks_to_wear_collection = total_polishes / polishes_per_week
        years_to_wear_collection = weeks_to_wear_collection / 52
        
        st.markdown(f"""
        <div style='background-color: #f0f8ff; padding: 20px; border-radius: 10px;'>
            <h4>Polishes in Collection Worn: {worn_polishes}</h4>
            <h4>Total Polishes in Collection: {total_polishes}</h4>
            <h4>Percent of Collection Worn: {percent_worn:.2f}%</h4>
            <h4>Total Days of Polish: {total_days}</h4>
            <h4>Polishes/Week: {polishes_per_week:.2f}</h4>
            <h4>Weeks to Wear Collection: {weeks_to_wear_collection:.2f}</h4>
            <h4>Years to Wear Collection: {years_to_wear_collection:.2f}</h4>
        </div>
        """, unsafe_allow_html=True)
        
        # Visual separator
        st.markdown("---")
        
        # Sync button
        if st.button("Calculate Favorites"):
            display_statistics()
    
    elif page == "Database":
        display_database()

if __name__ == "__main__":
    main() 
    