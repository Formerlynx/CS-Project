"""
Build script for creating standalone executable of Expense Tracker
Run this script to generate the executable
"""

import os
import subprocess
import sys

def create_spec_file():
    """Create PyInstaller spec file with all necessary configurations"""
    spec_content = """# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('templates', 'templates'),
        ('static', 'static'),
        ('Database', 'Database'),
    ],
    hiddenimports=[
        'flask',
        'matplotlib',
        'matplotlib.pyplot',
        'pyodbc',
        'flask_bcrypt',
        'bcrypt',
        'PIL',
        'PIL._imagingtk',
        'PIL._tkinter_finder',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='ExpenseTracker',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
"""
    
    with open('ExpenseTracker.spec', 'w') as f:
        f.write(spec_content)
    print("✓ Created ExpenseTracker.spec file")

def check_files():
    """Check if required files exist"""
    required_files = ['app.py', 'templates', 'static', 'Database']
    missing = []
    
    for file in required_files:
        if not os.path.exists(file):
            missing.append(file)
    
    if missing:
        print(f"\n❌ Missing required files/folders: {', '.join(missing)}")
        print("\nMake sure your project has:")
        print("  - app.py")
        print("  - templates/ folder")
        print("  - static/ folder")
        print("  - Database/ folder with expenses.accdb")
        return False
    
    print("✓ All required files found")
    return True

def install_requirements():
    """Install PyInstaller if not already installed"""
    print("\nChecking PyInstaller...")
    try:
        import pyinstaller # type: ignore
        print("✓ PyInstaller already installed")
    except ImportError:
        print("Installing PyInstaller...")
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'pyinstaller'])
        print("✓ PyInstaller installed")

def build_executable():
    """Build the executable using PyInstaller"""
    print("\nBuilding executable...")
    print("This may take 2-5 minutes...\n")
    
    try:
        # Use Python to run pyinstaller as a module
        result = subprocess.run(
            [sys.executable, '-m', 'PyInstaller', 'ExpenseTracker.spec', '--clean', '--noconfirm'],
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            print("Build output:")
            print(result.stdout)
            print("\nErrors:")
            print(result.stderr)
            raise Exception("Build failed")
        
        print("\n✓ Build complete!")
        
        exe_path = os.path.join(os.getcwd(), 'dist', 'ExpenseTracker.exe')
        if os.path.exists(exe_path):
            exe_size = os.path.getsize(exe_path) / (1024 * 1024)  # Size in MB
            print(f"\nExecutable created: {exe_path}")
            print(f"File size: {exe_size:.2f} MB")
        else:
            print("\n⚠ Warning: Could not find executable in dist folder")
            
    except Exception as e:
        print(f"\n❌ Build error: {e}")
        print("\nTrying alternative build method...")
        
        # Try direct pyinstaller command
        try:
            subprocess.check_call([
                'pyinstaller',
                '--onefile',
                '--add-data', 'templates;templates',
                '--add-data', 'static;static',
                '--add-data', 'Database;Database',
                '--hidden-import=flask',
                '--hidden-import=matplotlib',
                '--hidden-import=pyodbc',
                '--hidden-import=flask_bcrypt',
                '--name', 'ExpenseTracker',
                'app.py'
            ])
            print("\n✓ Build complete (alternative method)!")
        except Exception as e2:
            print(f"\n❌ Alternative build also failed: {e2}")
            raise

if __name__ == '__main__':
    print("=" * 60)
    print("Expense Tracker - Executable Builder")
    print("=" * 60)
    
    try:
        # Check if required files exist
        if not check_files():
            print("\n❌ Cannot proceed without required files!")
            input("\nPress Enter to exit...")
            sys.exit(1)
        
        install_requirements()
        create_spec_file()
        build_executable()
        
        print("\n" + "=" * 60)
        print("SUCCESS! Your executable is ready.")
        print("=" * 60)
        print("\nTo run your application:")
        print("1. Navigate to the 'dist' folder")
        print("2. Double-click 'ExpenseTracker.exe'")
        print("\nThe database is embedded - no external files needed!")
        print("User data will be stored in: %LOCALAPPDATA%\\ExpenseTracker")
        
        input("\nPress Enter to exit...")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("\nPlease check:")
        print("1. You have Python 3.8+ installed")
        print("2. All required files are in the project folder")
        print("3. You have write permissions in this directory")
        input("\nPress Enter to exit...")
        sys.exit(1)