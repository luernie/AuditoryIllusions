import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

# Read the CSV file
df = pd.read_csv('data/Illusions_Data.csv', index_col=0)

print("Original Data:")
print(df)
print("\n")

# Create a copy for normalized data
df_normalized = df.copy()

# Define subject groups
subject_groups = {
    'E': ['E1', 'E2', 'E3'],
    'R': ['R1', 'R2', 'R3'],
    'C': ['C1', 'C2', 'C3'],
    'L': ['L1', 'L2', 'L3'],
    'N': ['N1', 'N2', 'N3']
}

# Normalize by subject group
for group_name, indices in subject_groups.items():
    # Get all values for this subject group
    group_data = df.loc[indices]
    
    # Find min and max across all values in this group
    min_val = group_data.min().min()
    max_val = group_data.max().max()
    
    # Avoid division by zero if all values are the same
    if max_val - min_val == 0:
        df_normalized.loc[indices] = 0
    else:
        # Normalize: (value - min) / (max - min) * 10
        df_normalized.loc[indices] = ((group_data - min_val) / (max_val - min_val)) * 10

# Round to 2 decimal places
df_normalized = df_normalized.round(2)

print("Normalized Data:")
print(df_normalized)
print("\n")

# Save normalized data to CSV
output_path = 'data/Illusions_Data_Normalized.csv'
df_normalized.to_csv(output_path)
print(f"Normalized data saved to: {output_path}")

# Prepare data for grouped box plot
# Group participants by their trial number (1, 2, or 3)
participant_groups = {
    'H': ['E1', 'R1', 'C1', 'L1', 'N1'],      # Trial 1 across all subjects
    'AH': ['E2', 'R2', 'C2', 'L2', 'N2'],     # Trial 2 across all subjects
    'NH': ['E3', 'R3', 'C3', 'L3', 'N3']      # Trial 3 across all subjects
}

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
        
        # Create box plot (showfliers=False since we'll add points manually)
        bp = ax.boxplot(data_for_boxes, positions=positions, widths=width*0.8,
                       patch_artist=True, showfliers=False,
                       boxprops=dict(facecolor=colors[i], alpha=0.7),
                       medianprops=dict(color='black', linewidth=1.5),
                       whiskerprops=dict(color=colors[i]),
                       capprops=dict(color=colors[i]))
        box_plots.append(bp['boxes'][0])
        
        # Add individual data points (hollow circles, no jitter, aligned)
        for j, (pos, data) in enumerate(zip(positions, data_for_boxes)):
            # Create array of same position for all data points
            x_positions_scatter = np.full(len(data), pos)
            ax.scatter(x_positions_scatter, data, facecolors='none', edgecolors='black', 
                      linewidths=1.5, alpha=0.8, s=50, zorder=3)

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
plot_path = 'data/boxplot.png'
plt.savefig(plot_path, dpi=300, bbox_inches='tight')
print(f"Box plot saved to: {plot_path}")

plt.show()