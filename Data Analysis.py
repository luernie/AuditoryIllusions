import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

# Read the CSV file
df = pd.read_csv('/mnt/user-data/uploads/Illusions_Data_-_Sheet1.csv', index_col=0)

print("Original Data:")
print(df)
print("\n")

# Create a copy for normalized data
df_normalized = df.copy()

# Normalize each row (participant) so min=0 and max=10
for index, row in df.iterrows():
    min_val = row.min()
    max_val = row.max()
    
    # Avoid division by zero if all values are the same
    if max_val - min_val == 0:
        df_normalized.loc[index] = 0
    else:
        # Normalize: (value - min) / (max - min) * 10
        df_normalized.loc[index] = ((row - min_val) / (max_val - min_val)) * 10

# Round to 2 decimal places
df_normalized = df_normalized.round(2)

print("Normalized Data:")
print(df_normalized)
print("\n")

# Save normalized data to CSV
output_path = '/mnt/user-data/outputs/Illusions_Data_Normalized.csv'
df_normalized.to_csv(output_path)
print(f"Normalized data saved to: {output_path}")

# Prepare data for grouped box plot
# Group participants by their letter prefix
participant_groups = {
    'H': ['E1', 'E2', 'E3'],      # Healthy
    'AH': ['R1', 'R2', 'R3'],     # At-risk Healthy (assuming R = at-risk)
    'NH': ['C1', 'C2', 'C3']      # Non-Healthy (assuming C = condition)
}

# Map remaining participants if they exist
for idx in df_normalized.index:
    if idx.startswith('L'):
        if 'L' not in participant_groups:
            participant_groups['L'] = []
        if idx not in sum(participant_groups.values(), []):
            participant_groups.setdefault('L', []).append(idx)
    elif idx.startswith('N'):
        if 'N' not in participant_groups:
            participant_groups['N'] = []
        if idx not in sum(participant_groups.values(), []):
            participant_groups.setdefault('N', []).append(idx)

# Create the grouped box plot
fig, ax = plt.subplots(figsize=(14, 6))

conditions = df_normalized.columns.tolist()
group_labels = ['H', 'AH', 'NH']
colors = ['#3498db', '#e74c3c', '#2ecc71']  # Blue, Red, Green

# Calculate positions for box plots
num_conditions = len(conditions)
num_groups = len(group_labels)
width = 0.25
x_positions = np.arange(num_conditions)

# Store box plot objects for legend
box_plots = []

# Create box plots for each group
for i, group_label in enumerate(group_labels):
    if group_label in participant_groups:
        group_indices = participant_groups[group_label]
        # Get data for this group across all conditions
        data_for_boxes = [df_normalized.loc[group_indices, condition].values 
                         for condition in conditions]
        
        # Calculate positions for this group
        positions = x_positions + (i - 1) * width
        
        # Create box plot
        bp = ax.boxplot(data_for_boxes, positions=positions, widths=width*0.8,
                       patch_artist=True, showfliers=True,
                       boxprops=dict(facecolor=colors[i], alpha=0.7),
                       medianprops=dict(color='black', linewidth=1.5),
                       whiskerprops=dict(color=colors[i]),
                       capprops=dict(color=colors[i]))
        box_plots.append(bp['boxes'][0])

# Add vertical line separating risset from 60 conditions
separation_x = num_conditions - 1.5
ax.axvline(x=separation_x, color='black', linestyle='--', linewidth=2, alpha=0.5)

# Customize plot
ax.set_xlabel('Rhythm Types', fontsize=13, fontweight='bold')
ax.set_ylabel('Normalized Perceived Acceleration (beats per second²)', fontsize=13, fontweight='bold')
ax.set_title('Normalized Perceived Acceleration by Rhythm Type and Group', fontsize=14, fontweight='bold')
ax.set_xticks(x_positions)
ax.set_xticklabels(conditions, fontsize=11)
ax.legend(box_plots, group_labels, loc='upper left', fontsize=11)
ax.grid(True, alpha=0.3, axis='y')
ax.set_ylim(-0.5, 11)

plt.tight_layout()

# Save the plot
plot_path = '/mnt/user-data/outputs/boxplot.png'
plt.savefig(plot_path, dpi=300, bbox_inches='tight')
print(f"Box plot saved to: {plot_path}")

plt.show()