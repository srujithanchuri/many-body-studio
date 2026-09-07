"""
Codebase Packer for Gemini / LLMs
Combines all source code, documentation (AGENTS.md, README.md, etc.),
and configuration files into a single, clean .txt file with directory tree
and structured file delimiters.
"""

import os
import sys

ROOT_DIR = r"C:\Users\sruji\Projects\masters_thesis_gui"
OUTPUT_FILE = os.path.join(ROOT_DIR, "codebase_context.txt")

EXCLUDE_DIRS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    "build",
    "dist",
    ".idea",
    ".vscode",
    "results",
    "scratch",
    "many_body_results"
}

INCLUDE_EXTENSIONS = {
    ".py",
    ".md",
    ".bat",
    ".sh",
    ".toml",
    ".json",
    ".yaml",
    ".yml",
    ".ini",
    ".txt"
}

EXCLUDE_FILES = {
    "codebase_context.txt",
    "pack_codebase.py"
}


def build_file_list(root_dir):
    file_list = []
    for dirpath, dirnames, filenames in os.walk(root_dir):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
        
        for fname in sorted(filenames):
            if fname in EXCLUDE_FILES:
                continue
            ext = os.path.splitext(fname)[1].lower()
            if ext in INCLUDE_EXTENSIONS:
                abs_path = os.path.join(dirpath, fname)
                rel_path = os.path.relpath(abs_path, root_dir)
                file_list.append((rel_path, abs_path))
    return sorted(file_list, key=lambda x: x[0])


def generate_tree_string(file_list):
    tree_lines = ["DIRECTORY TREE:"]
    for rel_path, _ in file_list:
        tree_lines.append(f"  ├── {rel_path}")
    return "\n".join(tree_lines)


def pack_codebase():
    files = build_file_list(ROOT_DIR)
    print(f"Found {len(files)} text/code files to pack.")
    
    with open(OUTPUT_FILE, "w", encoding="utf-8") as out:
        out.write("=" * 80 + "\n")
        out.write("PROJECT CODEBASE CONTEXT FOR GEMINI / LLM\n")
        out.write(f"Root: {ROOT_DIR}\n")
        out.write(f"Total Files: {len(files)}\n")
        out.write("=" * 80 + "\n\n")
        
        out.write(generate_tree_string(files))
        out.write("\n\n" + "=" * 80 + "\n\n")
        
        for rel_path, abs_path in files:
            out.write(f"\n{'=' * 80}\n")
            out.write(f"FILE: {rel_path}\n")
            out.write(f"{'=' * 80}\n\n")
            
            try:
                with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
                    out.write(content)
                    if not content.endswith("\n"):
                        out.write("\n")
            except Exception as e:
                out.write(f"[ERROR READING FILE: {e}]\n")
                
    output_size = os.path.getsize(OUTPUT_FILE)
    est_tokens = output_size // 4
    print(f"\nSuccessfully generated: {OUTPUT_FILE}")
    print(f"File size: {output_size / 1024:.1f} KB (~{est_tokens:,} estimated tokens)")
    print("Ready for Gemini!")

if __name__ == "__main__":
    pack_codebase()
