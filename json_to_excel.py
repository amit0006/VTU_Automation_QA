import os
import re
import shutil
import json
import difflib
import sys 
from openpyxl import Workbook, load_workbook
from openpyxl.styles import PatternFill, Alignment, Font

# ==============================================
# CRITICAL FIX: Move normalize_code function to the top 
# so it can be used during argument parsing.
# ==============================================
def normalize_code(code):
    """Removes non-alphanumeric chars and uppercases for comparison."""
    if not code: return ""
    return re.sub(r"[^A-Z0-9]", "", str(code).upper())


# ==============================================
# CONFIGURATION
# ==============================================
JSON_INPUT_FOLDER = "gemini_json_results"
EXCEL_OUTPUT_FILENAME = "vtu_structured_results.xlsx"

# Hybrid Canonicalization Cutoffs
PERMISSIVE_CUTOFF = 0.86 
STRICT_CUTOFF = 0.99      

# ==============================================
# ARGUMENT PARSING
# ==============================================
FILTERED_SUBJECT_CODES_NORM = set()
SUBJECT_CODES_EXPLICIT = set() # Stores canonical codes provided by the user

if len(sys.argv) > 1:
    try:
        # The subject codes list is passed as a JSON string (sys.argv[1])
        subject_codes_list = json.loads(sys.argv[1])
        
        # Store normalized codes for both filtering and explicit header list
        for code in subject_codes_list:
             norm_code = normalize_code(code)
             FILTERED_SUBJECT_CODES_NORM.add(norm_code)
             SUBJECT_CODES_EXPLICIT.add(norm_code) # Use normalized code for strict headers
             
        print(f"📝 Filtering results for {len(FILTERED_SUBJECT_CODES_NORM)} subjects.")
    except json.JSONDecodeError:
        print("⚠️ Failed to parse subject codes argument. Processing all subjects found.")
    except Exception as e:
        # The previous NameError (now fixed by moving normalize_code) would hit here.
        print(f"⚠️ Error processing command-line arguments: {e}. Processing all subjects found.")

# ==============================================
# STEP 0: Setup Excel File 
# ==============================================

if os.path.exists(EXCEL_OUTPUT_FILENAME):
    print(f"🔄 Loading existing Excel file: {EXCEL_OUTPUT_FILENAME}")
    wb = load_workbook(EXCEL_OUTPUT_FILENAME)
    ws = wb.active
else:
    print(f"➕ Creating new Excel file: {EXCEL_OUTPUT_FILENAME}")
    wb = Workbook()
    ws = wb.active
    ws.title = "Results"
    
    # Set up initial header for USN
    header_font = Font(bold=True)
    ws.cell(row=1, column=1).value = "University Seat Number"
    ws.cell(row=1, column=1).font = header_font
    ws.merge_cells(start_row=1, start_column=1, end_row=2, end_column=1)
    ws.cell(row=1, column=1).alignment = Alignment(horizontal="center", vertical="center")


# ==============================================
# STEP 1: Helper Functions (Unchanged)
# ==============================================

def get_existing_subject_columns(ws):
    """Returns a map of {Subject Code: Column Index}."""
    subject_cols = {}
    for col in range(2, ws.max_column + 1, 4):
        code = ws.cell(row=1, column=col).value
        if code:
            subject_cols[code] = col
    return subject_cols

def get_next_empty_row(ws, usn):
    """Finds the row for a USN, either existing or the next empty one."""
    existing_usn_map = {ws.cell(row=i, column=1).value: i for i in range(3, ws.max_row + 2)}

    if usn in existing_usn_map:
        return existing_usn_map[usn]
    
    # Find the next truly empty row in column A
    for row in range(3, ws.max_row + 2):
        if ws.cell(row=row, column=1).value is None:
            return row
    return ws.max_row + 1

def ensure_and_sort_subject_headers(ws, new_codes):
    """Ensures all new codes have columns, keeps existing columns, and sorts them all."""
    header_font = Font(bold=True)
    existing_codes = list(get_existing_subject_columns(ws).keys())
    all_codes = existing_codes[:]
    for code in new_codes:
        if code and code not in all_codes:
            all_codes.append(code)

    all_codes.sort()

    # Clear old headers
    merged_to_unmerge = [str(m) for m in ws.merged_cells.ranges if m.min_row <= 2]
    for m in merged_to_unmerge:
        try: ws.unmerge_cells(m)
        except ValueError: pass

    if ws.max_column > 1:
        for col in range(2, ws.max_column + 1):
            ws.cell(row=1, column=col).value = None
            ws.cell(row=2, column=col).value = None

    # Recreate headers
    for i, code in enumerate(all_codes):
        col = 2 + (i * 4)
        ws.merge_cells(start_row=1, start_column=col, end_row=1, end_column=col + 3)
        
        cell1 = ws.cell(row=1, column=col)
        cell1.value = code
        cell1.alignment = Alignment(horizontal="center")
        cell1.font = header_font
        
        for j, name in enumerate(["Internal", "External", "Total", "Result"]):
            cell2 = ws.cell(row=2, column=col + j)
            cell2.value = name
            cell2.alignment = Alignment(horizontal="center")
            cell2.font = header_font

def canonicalize_code(raw_code, existing_codes):
    """
    Generalized Hybrid Canonicalization:
    Uses a strict cutoff for potential confusing codes, and a permissive one otherwise.
    """
    norm = normalize_code(raw_code)
    if not norm: return raw_code

    existing_norm_map = {normalize_code(c): c for c in existing_codes}

    # 1. Exact normalized match
    if norm in existing_norm_map:
        return existing_norm_map[norm]

    # Determine cutoff: Strict for codes matching the pattern of confusing VTU codes
    if 6 <= len(norm) <= 7 and re.match(r"[BCV][A-Z]{3}\d{3}", norm):
        cutoff = STRICT_CUTOFF # 0.99 for high stability
    else:
        cutoff = PERMISSIVE_CUTOFF # 0.86 for general typo correction (e.g., BCS405A vs BCS405A.)

    # 2. Fuzzy match
    close = difflib.get_close_matches(norm, list(existing_norm_map.keys()), n=1, cutoff=cutoff) 

    if close:
        return existing_norm_map[close[0]]
    else:
        # 3. New code
        return norm

# Define Fills for Excel
fill_red = PatternFill(start_color="FFFFC7CE", end_color="FFFFC7CE", fill_type="solid")
fill_green = PatternFill(start_color="FFC6EFCE", end_color="FFC6EFCE", fill_type="solid")
fill_yellow = PatternFill(start_color="FFFFEB9C", end_color="FFFFEB9C", fill_type="solid")


# ==============================================
# STEP 2: Main Processing Loop
# ==============================================

# Get all unique existing headers to use for canonicalization
existing_headers = set(get_existing_subject_columns(ws).keys())

# Collect all new unique canonical subject codes found across all JSON files
all_canonical_codes_found = set()
data_to_write = {} # {USN: {CanonicalCode: {Internal: 40, ...}}}

print("🔎 Starting JSON file iteration and data collection...")
json_files = [f for f in os.listdir(JSON_INPUT_FOLDER) if f.endswith('_gemini_output.json')]

if not json_files:
    print(f"⚠️ No JSON files found in '{JSON_INPUT_FOLDER}'. Exiting.")
    # Attempt to delete the folder even if empty
    if os.path.exists(JSON_INPUT_FOLDER):
        shutil.rmtree(JSON_INPUT_FOLDER)
        print(f"🗑️ Deleted empty folder: {JSON_INPUT_FOLDER}")
    exit()

for filename in json_files:
    json_path = os.path.join(JSON_INPUT_FOLDER, filename)
    
    print(f"   Processing file: {filename}") # Diagnostic print
    
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            json_output = json.load(f)
    except Exception as e:
        print(f"❌ Error reading or parsing JSON file {filename}: {e}. Skipping.")
        continue

    usn = (json_output.get("USN") or "NOTFOUND").strip().upper()
    if usn == "NOTFOUND":
        print(f"⚠️ USN not found in {filename}. Skipping.")
        continue

    # Ensure we don't process the same USN multiple times if different files exist for it
    if usn in data_to_write:
        print(f"⚠️ USN {usn} already processed. Skipping duplicate file {filename}.")
        continue

    data_to_write[usn] = {}
    
    # Process subjects in this JSON file
    for sub in json_output.get("Subjects", []):
        raw_code = sub.get("Code", "").strip()
        if not raw_code: continue

        # Canonicalize the extracted code
        current_canonical_set = existing_headers.union(all_canonical_codes_found)
        canon_code = canonicalize_code(raw_code, current_canonical_set) 
        
        # NEW FILTERING LOGIC: Only proceed if the code is in the filter list (or if no filter is set)
        if FILTERED_SUBJECT_CODES_NORM and normalize_code(canon_code) not in FILTERED_SUBJECT_CODES_NORM:
            print(f"   Skipping subject {raw_code} for {usn}: Not in filter list.")
            continue

        all_canonical_codes_found.add(canon_code)
        
        internal = sub.get("Internal")
        external = sub.get("External")
        total = sub.get("Total")
        result = sub.get("Result", "").strip().upper()

        if (total is None or total == "") and isinstance(internal, int) and isinstance(external, int):
            total = internal + external
            
        data_to_write[usn][canon_code] = {
            "Internal": internal,
            "External": external,
            "Total": total,
            "Result": result,
        }

print(f"✅ Collected data for {len(data_to_write)} unique USNs.")

# ==============================================
# STEP 3: Write Data to Excel
# ==============================================

# 1. Update headers with all collected canonical codes
print("✍️ Updating Excel headers...")

# 💡 FINAL HEADER LOGIC: Enforce the headers to be exactly the union of:
# 1. The explicit codes passed by the user (SUBJECT_CODES_EXPLICIT)
# 2. Any existing headers that match the filter (to preserve old data)
# 3. Any canonical codes found in this run (all_canonical_codes_found)

headers_to_use = set()

if FILTERED_SUBJECT_CODES_NORM:
    # 1. Add all canonical codes found in the JSONs (which are already filtered)
    headers_to_use.update(all_canonical_codes_found)
    
    # 2. Add all *existing* Excel headers that are in the filter list (to preserve existing data)
    for h in existing_headers:
        if normalize_code(h) in FILTERED_SUBJECT_CODES_NORM:
            headers_to_use.add(h)
    
    # 3. Add the explicitly passed normalized codes as headers (CRITICAL: Ensures all expected columns exist)
    headers_to_use.update(SUBJECT_CODES_EXPLICIT)
    
    # NOTE: headers_to_use now contains all subjects that belong to the filter, 
    # whether found in JSONs or explicitly passed.
    
else:
    # Use all codes found and all existing codes if no filter is applied
    headers_to_use = all_canonical_codes_found.union(existing_headers)
    
ensure_and_sort_subject_headers(ws, headers_to_use)
subject_cols = get_existing_subject_columns(ws)

# 2. Iterate through collected data and write to sheet
print("✍️ Writing marks to Excel sheet...")
for usn, subjects in data_to_write.items():
    
    # Find the correct row for this USN
    row = get_next_empty_row(ws, usn)
    ws.cell(row=row, column=1).value = usn # Write USN (or overwrite if updating)

    # Write new subject data
    for code, info in subjects.items():
        if code in subject_cols:
            col = subject_cols[code]
            
            # Clear the old data in the 4 cells for this specific subject
            # This is correct: we only clear and update the column we are writing to.
            for offset in range(4):
                 ws.cell(row=row, column=col + offset).value = None
                 ws.cell(row=row, column=col + offset).fill = PatternFill(fill_type=None) # Clear color

            # Write marks
            for i, key in enumerate(["Internal", "External", "Total"]):
                value = info.get(key, "")
                try:
                    cell_value = int(value)
                except (ValueError, TypeError):
                    cell_value = value
                
                ws.cell(row=row, column=col + i).value = cell_value
                
            # Write Result and apply color fill
            result_cell = ws.cell(row=row, column=col + 3)
            result = info.get("Result", "").upper()
            result_cell.value = result
            
            if result == "F":
                result_cell.fill = fill_red
            elif result == "P":
                result_cell.fill = fill_green
            elif result == "A":
                result_cell.fill = fill_yellow

# 3. Save the Excel file
try:
    wb.save(EXCEL_OUTPUT_FILENAME)
    print(f"✅ Successfully processed all JSON files and saved data to: {EXCEL_OUTPUT_FILENAME}")
except Exception as e:
    print(f"❌ ERROR: Could not save Excel file. Please ensure '{EXCEL_OUTPUT_FILENAME}' is closed. Error: {e}")


# ==============================================
# STEP 4: CLEANUP
# ==============================================
if os.path.exists(JSON_INPUT_FOLDER):
    try:
        shutil.rmtree(JSON_INPUT_FOLDER)
        print(f"🗑️ Successfully deleted temporary folder: {JSON_INPUT_FOLDER}")
    except OSError as e:
        print(f"❌ ERROR: Could not delete folder {JSON_INPUT_FOLDER}. Check permissions or file locks. Error: {e}")