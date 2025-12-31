#!/usr/bin/env python3
"""
Script to add projected onboarding dates to the SBP Database CSV.

Logic:
- Skip the first row of each repository (base branch already onboarded)
- Fixed global daily budget = 300,000 * 11 repos = 3,300,000 LOC
- Per-repo budget = global budget / active repos
- As repos finish, remaining repos get higher per-repo budgets
- Day 1 is December 18, 2025 (Thursday)
- Also generates a daily LOC summary CSV
"""

import csv
from datetime import datetime, timedelta
from collections import defaultdict

# Configuration
CSV_PATH = "/Users/jackblundin/SWE-bench_Pro-os/Setup Scripts/loc_results/SBP Database - Bug Fix Status.csv"
OUTPUT_PATH = "/Users/jackblundin/SWE-bench_Pro-os/Setup Scripts/loc_results/SBP Database - Bug Fix Status.csv"
DAILY_SUMMARY_PATH = "/Users/jackblundin/SWE-bench_Pro-os/Setup Scripts/loc_results/daily_onboarding_summary.csv"

# Fixed global daily budget
TOTAL_REPOS = 11
GLOBAL_DAILY_BUDGET = 2000000  # 2 million LOC per day

# Start date: December 19, 2025
START_DATE = datetime(2025, 12, 19)


def parse_loc_delta(value):
    """Parse LOC_Delta value, handling N/A and empty values."""
    if not value or value == 'N/A' or value.strip() == '':
        return 0
    try:
        return int(value)
    except ValueError:
        return 0


def main():
    # Read with csv module to handle the complex format
    rows = []
    with open(CSV_PATH, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        for row in reader:
            rows.append(row)
    
    # Find the header row (contains "shortened_instance_id")
    header_idx = 0
    for i, row in enumerate(rows):
        if any('shortened_instance_id' in str(cell) for cell in row):
            header_idx = i
            break
    
    header = rows[header_idx]
    data_rows = rows[header_idx + 1:]
    
    # Remove existing "Projected onboarding date" column if present
    proj_date_idx = None
    for i, col in enumerate(header):
        if 'projected onboarding date' in col.lower():
            proj_date_idx = i
            break
    
    if proj_date_idx is not None:
        header = header[:proj_date_idx] + header[proj_date_idx+1:]
        data_rows = [row[:proj_date_idx] + row[proj_date_idx+1:] if len(row) > proj_date_idx else row for row in data_rows]
    
    # Find column indices
    loc_delta_idx = None
    repo_idx = None
    shortened_id_idx = None
    
    for i, col in enumerate(header):
        col_lower = col.lower().strip()
        if 'loc_delta' in col_lower:
            loc_delta_idx = i
        if col_lower == 'repo':
            repo_idx = i
        if 'shortened_instance_id' in col_lower:
            shortened_id_idx = i
    
    print(f"Header columns: {len(header)}")
    print(f"LOC_Delta column index: {loc_delta_idx}")
    print(f"Repo column index: {repo_idx}")
    print(f"Shortened ID column index: {shortened_id_idx}")
    print(f"Global daily budget: {GLOBAL_DAILY_BUDGET:,} LOC")
    
    # First, collect all branches per repo (excluding base branches)
    repo_branches = defaultdict(list)  # repo -> [(row_idx, loc_delta), ...]
    base_branches = {}  # Track which repos we've seen (first occurrence is base) -> row_idx
    
    for i, row in enumerate(data_rows):
        if len(row) <= max(loc_delta_idx or 0, repo_idx or 0, shortened_id_idx or 0):
            continue
        
        shortened_id = row[shortened_id_idx].strip() if shortened_id_idx is not None else ''
        repo = row[repo_idx].strip() if repo_idx is not None else ''
        loc_delta_str = row[loc_delta_idx].strip() if loc_delta_idx is not None else ''
        
        if not shortened_id or not repo:
            continue
        
        loc_delta = parse_loc_delta(loc_delta_str)
        
        # Skip first row of each repo (base branch) and record its index
        if repo not in base_branches:
            base_branches[repo] = i
            continue
        
        repo_branches[repo].append((i, loc_delta, shortened_id))
    
    # Initialize state for each repo
    repo_state = {}
    for repo in repo_branches:
        repo_state[repo] = {
            'branch_idx': 0,  # Index into repo_branches[repo]
            'running_sum': 0,
            'finished': False
        }
    
    # Track dates for each row
    row_dates = [''] * len(data_rows)
    
    # Mark base branches with "Base Branch"
    for repo, row_idx in base_branches.items():
        row_dates[row_idx] = 'Base Branch'
    
    # Track daily totals
    daily_loc = defaultdict(int)
    
    current_day = 1
    
    # Process day by day until all repos are done
    while True:
        active_repos = [r for r in repo_state if not repo_state[r]['finished']]
        if not active_repos:
            break
        
        # Calculate per-repo budget for this day
        per_repo_budget = GLOBAL_DAILY_BUDGET / len(active_repos)
        
        print(f"\nDay {current_day}: {len(active_repos)} active repos, {per_repo_budget:,.0f} LOC per repo")
        
        # Check which repos will finish this day (before processing)
        # This is needed to recalculate budget mid-day if repos finish
        repos_finishing_today = []
        
        for repo in active_repos:
            state = repo_state[repo]
            branches = repo_branches[repo]
            
            # Reset running sum for new day
            state['running_sum'] = 0
            
            # Assign branches to this day until we hit the per-repo budget
            while state['branch_idx'] < len(branches):
                row_idx, loc_delta, shortened_id = branches[state['branch_idx']]
                
                # Check if adding this branch would exceed budget
                if state['running_sum'] + loc_delta > per_repo_budget and state['running_sum'] > 0:
                    # Don't add this branch, it goes to next day
                    break
                
                # Add this branch to current day
                state['running_sum'] += loc_delta
                state['branch_idx'] += 1
                
                # Assign date to this row
                onboarding_date = START_DATE + timedelta(days=current_day - 1)
                date_str = onboarding_date.strftime('%m/%d/%Y')
                row_dates[row_idx] = date_str
                
                # Add to daily total
                daily_loc[current_day] += loc_delta
            
            # Check if repo is finished
            if state['branch_idx'] >= len(branches):
                state['finished'] = True
                repos_finishing_today.append(repo)
        
        if repos_finishing_today:
            print(f"  Repos finishing: {', '.join(repos_finishing_today)}")
        
        current_day += 1
        
        # Safety check to prevent infinite loop
        if current_day > 100:
            print("WARNING: Exceeded 100 days, breaking")
            break
    
    # Add header for new column
    header.append('Projected onboarding date')
    
    # Add dates to rows
    for i, row in enumerate(data_rows):
        row.append(row_dates[i])
    
    # Write updated CSV
    with open(OUTPUT_PATH, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(header)
        for row in data_rows:
            writer.writerow(row)
    
    print(f"\nUpdated CSV saved to: {OUTPUT_PATH}")
    
    # Write daily summary CSV
    with open(DAILY_SUMMARY_PATH, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Day', 'Date', 'Projected_LOC_Onboarded'])
        
        for day_num in sorted(daily_loc.keys()):
            date = START_DATE + timedelta(days=day_num - 1)
            date_str = date.strftime('%m/%d/%Y')
            writer.writerow([day_num, date_str, daily_loc[day_num]])
    
    print(f"Daily summary saved to: {DAILY_SUMMARY_PATH}")
    
    # Print summary
    print("\n" + "="*60)
    print("Daily Onboarding Summary")
    print("="*60)
    total_loc = 0
    for day_num in sorted(daily_loc.keys()):
        date = START_DATE + timedelta(days=day_num - 1)
        date_str = date.strftime('%m/%d/%Y')
        loc = daily_loc[day_num]
        total_loc += loc
        print(f"Day {day_num:2d} ({date_str}): {loc:>12,} LOC")
    
    print("-"*60)
    print(f"Total: {total_loc:,} LOC across {len(daily_loc)} days")
    
    # Print per-repo completion dates
    print("\n" + "="*60)
    print("Repository Completion Dates")
    print("="*60)
    for repo in sorted(repo_branches.keys()):
        branches = repo_branches[repo]
        if branches:
            last_row_idx = branches[-1][0]
            last_date = row_dates[last_row_idx]
            total_loc_repo = sum(b[1] for b in branches)
            print(f"{repo}: {last_date} ({len(branches)} branches, {total_loc_repo:,} LOC)")


if __name__ == "__main__":
    main()
