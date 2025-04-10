import pandas as pd
import random
from openpyxl import load_workbook
from openpyxl import writer
from openpyxl import reader

# Load the Excel sheet into a pandas DataFrame
file_path = '/Users/KatMcMillan/Documents/Documents/Personal/NPS.xlsx'
sheet_name = 'Original_Swatches'  # Update with your sheet name
file_output = '/Users/KatMcMillan/Documents/Documents/Personal/NPS_Selections.xlsx'
df = pd.read_excel(file_path, sheet_name, engine='openpyxl')
previous_selection_df = pd.read_excel(file_output, sheet_name="Selections", engine="openpyxl")
previous_selections = set({num for num in previous_selection_df["Number"].unique()})

# Initialize a set to keep track of previously selected polish Numbers and a list for past selections
past_selections = [df.loc[df["Number"] == ps] for ps in previous_selections]

def select_random_polish(df, previous_selections):
    # Filter out previously selected polish Numbers
    available_polishes = df[~df['Number'].isin(previous_selections)]
    
    # Check if there are available polishes to select from
    if available_polishes.empty:
        return None
    
    # Select a random polish from the available ones
    random_index = random.choice(available_polishes.index)
    random_polish = available_polishes.loc[[random_index]]
    
    # Update the set of previous selections
    previous_selections.add(random_polish.iloc[0]['Number'])
    
    return random_polish

# Select a random polish without repeating previous 15 selections
random_polish = select_random_polish(df, previous_selections)
if random_polish is not None:
    print("Random Polish:", random_polish.iloc[0]['Brand'], random_polish.iloc[0]['Shade Name'])
    print("Past Selections:", [past.iloc[0]['Brand'] + ' ' + past.iloc[0]['Shade Name'] for past in past_selections])
    print()
    past_selections.append(random_polish)

# Create a new DataFrame with the current and past selections
selections_df = pd.concat([previous_selection_df, random_polish])

# Load the existing workbook using openpyxl
with pd.ExcelWriter(file_output, engine='openpyxl') as writer:
    # Write the selections DataFrame to a new sheet in the same Excel workbook
    sheet_name_output = 'Selections'  # Update with your desired sheet name
    selections_df.to_excel(writer, sheet_name=sheet_name_output, index=False)
