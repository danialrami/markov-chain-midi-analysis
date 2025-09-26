#!/bin/bash

# Function to display usage
usage() {
    echo "MIDI File Copier Script (Flattened)"
    echo "This script will copy all MIDI files from a directory and its subdirectories"
    echo "to ~/Downloads/{folder-name}_midi/ (all files in same directory level)"
    echo
}

# Function to clean input (remove single quotes)
clean_input() {
    echo "$1" | sed "s/'//g"
}

# Function to get the base folder name from a path
get_folder_name() {
    basename "$1"
}

# Function to handle duplicate filenames
get_unique_filename() {
    local dest_dir="$1"
    local filename="$2"
    local base_name="${filename%.*}"
    local extension="${filename##*.}"
    local counter=1
    local new_filename="$filename"
    
    # Check if file already exists and create unique name if needed
    while [ -f "$dest_dir/$new_filename" ]; do
        new_filename="${base_name}_${counter}.${extension}"
        ((counter++))
    done
    
    echo "$new_filename"
}

# Main script starts here
echo "=== MIDI File Copier (Flattened) ==="
echo

# Prompt user for input filepath
read -p "Enter the filepath to search for MIDI files: " input_path

# Clean the input (remove single quotes)
clean_path=$(clean_input "$input_path")

# Expand tilde if present
eval clean_path="$clean_path"

# Check if the directory exists
if [ ! -d "$clean_path" ]; then
    echo "Error: Directory '$clean_path' does not exist."
    exit 1
fi

# Get the folder name for the destination directory
folder_name=$(get_folder_name "$clean_path")
dest_dir="$HOME/Downloads/${folder_name}_midi"

# Create destination directory if it doesn't exist
if [ ! -d "$dest_dir" ]; then
    mkdir -p "$dest_dir"
    echo "Created destination directory: $dest_dir"
else
    echo "Using existing destination directory: $dest_dir"
fi

# Counter for found files
count=0
duplicate_count=0

echo
echo "Searching for MIDI files in: $clean_path"
echo "Copying all files to same level in: $dest_dir"
echo

# Find and copy all MIDI files (.mid and .midi extensions, case insensitive)
while IFS= read -r -d '' file; do
    # Get just the filename (no path)
    original_filename=$(basename "$file")
    
    # Get unique filename in case of duplicates
    unique_filename=$(get_unique_filename "$dest_dir" "$original_filename")
    
    # Set destination file path
    dest_file="$dest_dir/$unique_filename"
    
    # Copy the file
    cp "$file" "$dest_file"
    
    # Increment counter and show progress
    ((count++))
    
    # Check if filename was changed due to duplicate
    if [ "$original_filename" != "$unique_filename" ]; then
        ((duplicate_count++))
        echo "Copied: $file -> $unique_filename (renamed due to duplicate)"
    else
        echo "Copied: $file -> $original_filename"
    fi
    
done < <(find "$clean_path" -type f \( -iname "*.mid" -o -iname "*.midi" \) -print0)

# Final summary
echo
if [ $count -eq 0 ]; then
    echo "No MIDI files found in the specified directory."
    # Remove empty destination directory
    rmdir "$dest_dir" 2>/dev/null
else
    echo "Successfully copied $count MIDI file(s) to $dest_dir"
    if [ $duplicate_count -gt 0 ]; then
        echo "Note: $duplicate_count file(s) were renamed to avoid filename conflicts"
    fi
    echo "All files are now at the same directory level."
fi
