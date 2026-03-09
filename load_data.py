import pyarrow.parquet as pq
import pandas as pd
import os

# Map configuration for coordinate conversion
MAP_CONFIG = {
    'AmbroseValley': {'scale': 900,  'origin_x': -370, 'origin_z': -473},
    'GrandRift':     {'scale': 581,  'origin_x': -290, 'origin_z': -290},
    'Lockdown':      {'scale': 1000, 'origin_x': -500, 'origin_z': -500},
}

def world_to_pixel(x, z, map_id):
    """Convert world coordinates to minimap pixel coordinates."""
    cfg = MAP_CONFIG.get(map_id)
    if not cfg:
        return None, None
    u = (x - cfg['origin_x']) / cfg['scale']
    v = (z - cfg['origin_z']) / cfg['scale']
    px = u * 1024
    py = (1 - v) * 1024
    return px, py

def load_all_data(base_path='.'):
    """Load all parquet files from all date folders into one DataFrame."""
    date_folders = [
        'February_10', 'February_11', 'February_12',
        'February_13', 'February_14'
    ]
    
    all_frames = []
    total_files = 0
    failed_files = 0

    for date_folder in date_folders:
        folder_path = os.path.join(base_path, date_folder)
        if not os.path.exists(folder_path):
            print(f"Skipping {folder_path} — not found")
            continue

        files = os.listdir(folder_path)
        print(f"Reading {len(files)} files from {date_folder}...")

        for filename in files:
            filepath = os.path.join(folder_path, filename)
            try:
                table = pq.read_table(filepath)
                df = table.to_pandas()

                # Decode event column from bytes to string
                df['event'] = df['event'].apply(
                    lambda x: x.decode('utf-8') if isinstance(x, bytes) else x
                )

                # Tag bots vs humans based on user_id format
                df['is_bot'] = df['user_id'].apply(
                    lambda uid: str(uid).isdigit()
                )

                # Add date label
                df['date'] = date_folder

                all_frames.append(df)
                total_files += 1

            except Exception as e:
                print(f"  Failed to read {filename}: {e}")
                failed_files += 1

    if not all_frames:
        print("No data loaded!")
        return pd.DataFrame()

    print(f"\nCombining {total_files} files...")
    combined = pd.concat(all_frames, ignore_index=True)

    # Convert pixel coordinates
    print("Converting coordinates...")
    combined[['px', 'py']] = combined.apply(
        lambda row: pd.Series(world_to_pixel(row['x'], row['z'], row['map_id'])),
        axis=1
    )

    # Clean match_id (strip .nakama-0 suffix)
    combined['match_id_clean'] = combined['match_id'].str.replace('.nakama-0', '', regex=False)

    print(f"\nDone! Loaded {len(combined):,} rows from {total_files} files.")
    print(f"Failed: {failed_files} files")
    print(f"\nEvent types:\n{combined['event'].value_counts()}")
    print(f"\nMaps:\n{combined['map_id'].value_counts()}")
    print(f"\nDates:\n{combined['date'].value_counts()}")

    # Save to parquet for fast loading in the app
    output_path = 'all_data.parquet'
    combined.to_parquet(output_path, index=False)
    print(f"\nSaved to {output_path}")

    return combined

if __name__ == '__main__':
    df = load_all_data()