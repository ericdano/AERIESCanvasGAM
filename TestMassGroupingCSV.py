import pandas as pd
import os

# 1. Create a large sample DataFrame
# This simulates the data you would be working with.
# It has three key columns: SEM (Semester), GR (Grade), and SC (School).
# We'll group by SC and GR, meaning each unique combination of these
# will result in its own CSV file.
data = {
    'Student_ID': range(100),
    'SEM': ['Fall 2023', 'Spring 2024'] * 50,
    'GR': ['A', 'B', 'C', 'D'] * 25,
    'SC': ['High School', 'Middle School'] * 50,
    'Score': [85, 92, 78, 95] * 25,
}
df = pd.DataFrame(data)

# 2. Group the DataFrame by the 'SC' and 'GR' columns
# The `groupby()` method returns a GroupBy object, which is
# an iterable that yields a tuple for each group. The first
# element of the tuple is the group name (a tuple of the
# grouping values), and the second is the sub-DataFrame for that group.
print("Grouping DataFrame by 'SC' and 'GR'...")
grouped = df.groupby(['SC', 'GR'])

# 3. Create a directory to store the output CSVs if it doesn't exist
output_dir = 'grouped_data_csvs'
if not os.path.exists(output_dir):
    os.makedirs(output_dir)
    print(f"Created directory: {output_dir}")

# 4. Loop through each group and save it as a separate CSV file
print("Iterating through groups and creating CSVs...")
for name, group_df in grouped:
    # The 'name' is a tuple, e.g., ('High School', 'A')
    # We construct a clean filename from these values.
    # The '.join(name)' method combines the tuple elements into a string,
    # and '.replace(' ', '_')' handles any spaces in the names.
    file_name = f"{'_'.join(name).replace(' ', '_')}.csv"
    output_path = os.path.join(output_dir, file_name)

    # Use the `to_csv()` method to save the group's DataFrame.
    # We select only the 'SEM' column before saving.
    # `index=False` prevents pandas from writing the DataFrame's
    # index as a column in the CSV, which is usually not desired.
    group_df[['SEM']].to_csv(output_path, index=False)
    print(f"Saved {output_path}")

print("\nProcess complete.")