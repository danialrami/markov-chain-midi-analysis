#!/bin/bash

# Function to display usage
usage() {
    echo "MIDI File Copier Script"
    echo "This script will copy all MIDI files from a directory and its subdirectories"
    echo "to ~/Downloads/{folder-name}_midi/"
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

# Main script starts here
echo "=== MIDI File Copier ==="
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

echo
echo "Searching for MIDI files in: $clean_path"
echo "Copying to: $dest_dir"
echo

# Find and copy all MIDI files (.mid and .midi extensions, case insensitive)
while IFS= read -r -d '' file; do
    # Get the relative path from the source directory
    rel_path=${file#$clean_path/}
    
    # Create the destination path
    dest_file="$dest_dir/$rel_path"
    
    # Create destination subdirectory if needed
    dest_subdir=$(dirname "$dest_file")
    if [ ! -d "$dest_subdir" ]; then
        mkdir -p "$dest_subdir"
    fi
    
    # Copy the file
    cp "$file" "$dest_file"
    
    # Increment counter and show progress
    ((count++))
    echo "Copied: $rel_path"
    
done < <(find "$clean_path" -type f \( -iname "*.mid" -o -iname "*.midi" \) -print0)

# Final summary
echo
if [ $count -eq 0 ]; then
    echo "No MIDI files found in the specified directory."
    # Remove empty destination directory
    rmdir "$dest_dir" 2>/dev/null
else
    echo "Successfully copied $count MIDI file(s) to $dest_dir"
fi
