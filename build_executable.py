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
        'pyodbc',
        'flask_bcrypt',
        'bcrypt',
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
    console=True,  # Set to False to hide console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # Add path to .ico file if you have one
)
"""
    
    with open('ExpenseTracker.spec', 'w') as f:
        f.write(spec_content)
    print("✓ Created ExpenseTracker.spec file")

def install_requirements():
    """Install PyInstaller if not already installed"""
    print("\nInstalling PyInstaller...")
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'pyinstaller'])
    print("✓ PyInstaller installed")

def build_executable():
    """Build the executable using PyInstaller"""
    print("\nBuilding executable...")
    subprocess.check_call(['pyinstaller', 'ExpenseTracker.spec', '--clean'])
    print("\n✓ Build complete!")
    print(f"\nExecutable location: {os.path.join(os.getcwd(), 'dist', 'ExpenseTracker.exe')}")

if __name__ == '__main__':
    print("=" * 60)
    print("Expense Tracker - Executable Builder")
    print("=" * 60)
    
    try:
        install_requirements()
        create_spec_file()
        build_executable()
        
        print("\n" + "=" * 60)
        print("SUCCESS! Your executable is ready.")
        print("=" * 60)
        print("\nTo run your application:")
        print("1. Navigate to the 'dist' folder")
        print("2. Double-click 'ExpenseTracker.exe'")
        print("\nNote: The Database folder must be in the same directory as the executable")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)