import streamlit as st
import pandas as pd
import random
from tqdm import tqdm
import os
from datetime import datetime
import time
import logging
import sqlite3

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

# Define the absolute path for the database
DB_PATH = os.path.join(os.path.dirname(__file__), 'votes.db')

# Connect to SQLite database
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Create table for votes
cursor.execute('''
CREATE TABLE IF NOT EXISTS votes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    number TEXT,
    brand TEXT,
    shade_name TEXT,
    finish TEXT,
    collection TEXT,
    winner_number TEXT,
    winner_brand TEXT,
    winner_shade_name TEXT,
    winner_finish TEXT,
    winner_collection TEXT
)
''')
conn.commit()

@st.cache_data
def load_data():
    """Load and return the polish collection, history, and previous selections"""
    with st.spinner('Loading data...'):
        # Load the full collection
        collection_df = pd.read_excel(COLLECTION_FILE, sheet_name=COLLECTION_SHEET, engine='openpyxl')
        # Ensure all necessary columns are present
        expected_columns = ['Number', 'Brand', 'Shade Name', 'Description', 'Finish', 'Notes']
        for col in expected_columns:
            if col not in collection_df.columns:
                collection_df[col] = ''
        # Replace all NaN values with empty strings
        collection_df = collection_df.fillna('')
        
        # Load history data
        history_df = pd.read_excel(COLLECTION_FILE, sheet_name=HISTORY_SHEET, engine='openpyxl', usecols='F:N')
        history_df.columns = ['Date', 'Number', 'Brand', 'Shade Name', 'Description', 'Finish', 'L', 'M', 'Notes']
        # Clean up the data
        history_df['Brand'] = history_df['Brand'].fillna('Unknown')
        history_df['Date'] = pd.to_datetime(history_df['Date'], errors='coerce')
        # Remove entries without dates
        history_df = history_df.dropna(subset=['Date'])
        # Replace all remaining NaN values with empty strings
        history_df = history_df.fillna('')
        
        # Load previous selections (just numbers)
        try:
            selections_df = pd.read_excel(SELECTIONS_FILE, sheet_name=SELECTIONS_SHEET, engine='openpyxl')
            # Ensure we have the Number column
            if 'Number' not in selections_df.columns:
                selections_df = pd.DataFrame(columns=['Number', 'Votes'])
            if 'Votes' not in selections_df.columns:
                selections_df['Votes'] = 1
            # Replace all NaN values with empty strings
            selections_df = selections_df.fillna('')
        except:
            selections_df = pd.DataFrame(columns=['Number', 'Votes'])
            
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

def save_vote(selected_polish):
    """Save the vote to the selections file"""
    _, selections_df, _, _ = load_data()
    
    # Ensure Number column is string type
    selected_polish['Number'] = str(selected_polish['Number'])
    
    # Check if the polish has been selected before
    if selected_polish['Number'] in selections_df['Number'].values:
        # Increment vote count
        selections_df.loc[selections_df['Number'] == selected_polish['Number'], 'Votes'] += 1
    else:
        # Add new selection with initial vote
        new_selection = pd.DataFrame([{
            'Number': selected_polish['Number'],
            'Votes': 1
        }])
        selections_df = pd.concat([selections_df, new_selection], ignore_index=True)
    
    # Save to Excel using openpyxl
    with pd.ExcelWriter(SELECTIONS_FILE, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
        selections_df.to_excel(writer, sheet_name=SELECTIONS_SHEET, index=False)
    
    st.cache_data.clear()

def record_vote(selected_polish, polishes):
    try:
        with sqlite3.connect(DB_PATH) as conn:  # Use the absolute path
            cursor = conn.cursor()
            for polish in polishes:
                logging.debug(f"Attempting to insert vote for polish: {polish['Number']}")
                cursor.execute('''
                INSERT INTO votes (number, brand, shade_name, finish, collection, winner_number, winner_brand, winner_shade_name, winner_finish, winner_collection)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    polish['Number'], polish['Brand'], polish['Shade Name'], polish['Finish'], polish.get('Collection', ''),
                    selected_polish['Number'], selected_polish['Brand'], selected_polish['Shade Name'], selected_polish['Finish'], selected_polish.get('Collection', '')
                ))
            conn.commit()
            logging.debug("Vote committed to the database.")
            
            # Verify the vote is saved
            cursor.execute('SELECT COUNT(*) FROM votes')
            count = cursor.fetchone()[0]
            logging.debug(f"Total votes in database: {count}")
            st.success(f"Vote recorded! Total votes: {count}")
    except Exception as e:
        logging.error(f"Error recording vote: {e}")
        st.error("Failed to record vote. Please try again.")

def calculate_statistics():
    with sqlite3.connect(DB_PATH) as conn:
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

def init_db():
    conn = sqlite3.connect(DB_PATH)  # Use the absolute path
    cursor = conn.cursor()
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS votes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        number TEXT,
        brand TEXT,
        shade_name TEXT,
        finish TEXT,
        collection TEXT,
        winner_number TEXT,
        winner_brand TEXT,
        winner_shade_name TEXT,
        winner_finish TEXT,
        winner_collection TEXT
    )
    ''')
    conn.commit()
    conn.close()

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

def main():
    init_db()  # Initialize the database
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
                    <div style='padding: 20px; border-radius: 10px; background-color: #f8f9fa; margin-bottom: 20px;'>
                        <h3>{polish['Brand']}</h3>
                        <p><strong>Shade:</strong> {polish['Shade Name']}</p>
                        <p><strong>Finish:</strong> {polish['Finish']}</p>
                        <p><strong>Description:</strong> {polish['Description']}</p>
                        {collection_info}
                    </div>
                    """, unsafe_allow_html=True)
                    
                    if st.button("Select this polish", key=f"select_{polish['Number']}"):
                        record_vote(polish, random_polishes.to_dict('records'))
                        st.success("Selection recorded! Refreshing...")
                        time.sleep(1)
                        st.experimental_rerun()
    
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
        st.subheader("Database View")
        
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM votes")
            rows = cursor.fetchall()
            
            # Convert to DataFrame for display
            db_df = pd.DataFrame(rows, columns=['ID', 'Number', 'Brand', 'Shade Name', 'Finish', 'Collection', 
                                                'Winner Number', 'Winner Brand', 'Winner Shade Name', 'Winner Finish', 'Winner Collection'])
            
            st.dataframe(db_df, hide_index=True, use_container_width=True)

if __name__ == "__main__":
    main() 
    