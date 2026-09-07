import os
import sys
import shutil
import subprocess
from pathlib import Path

def main():
    gui_root = Path(__file__).resolve().parents[1]
    project_root = gui_root.parent / 'masters_thesis'
    dist_dir = gui_root / 'dist' / 'ManyBodyStudio'
    build_dir = gui_root / 'build'

    print('=' * 72)
    print('  Many-Body Studio - Standalone CPU onedir Builder [Beta v1]')
    print('=' * 72)
    print(f'GUI Root:     {gui_root}')
    print(f'Physics Root: {project_root}')
    print()

    # 1. Ensure pyinstaller is installed
    print('[1/5] Checking PyInstaller...')
    try:
        import PyInstaller
        print(f'      PyInstaller {PyInstaller.__version__} is available.')
    except ImportError:
        print('      PyInstaller not found. Installing into environment...')
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'pyinstaller'])

    # 1b. Ensure latest high-DPI icons are generated
    print('      Ensuring razor-sharp multi-resolution icon assets are up to date...')
    build_icons_script = gui_root / 'tools' / 'build_icons.py'
    if build_icons_script.exists():
        subprocess.check_call([sys.executable, str(build_icons_script)])

    # 2. Clean previous builds
    print('[2/5] Cleaning previous build artifacts...')
    def _safe_remove_dir(p):
        if not p.exists():
            return
        import stat
        for root, dirs, files in os.walk(p, topdown=False):
            for f in files:
                fp = os.path.join(root, f)
                try:
                    os.chmod(fp, stat.S_IWRITE)
                    os.remove(fp)
                except Exception:
                    pass
            for d in dirs:
                dp = os.path.join(root, d)
                try:
                    os.chmod(dp, stat.S_IWRITE)
                    os.rmdir(dp)
                except Exception:
                    pass
        try:
            os.chmod(p, stat.S_IWRITE)
            os.rmdir(p)
        except Exception:
            pass

    _safe_remove_dir(build_dir)
    _safe_remove_dir(dist_dir)

    # 3. Assemble PyInstaller command
    print('[3/5] Compiling CPU-only standalone package...')
    print('      (Excluding CuPy/CUDA drivers to produce a lightweight ~350 MB bundle)')
    print()

    entry_point = str(gui_root / 'pyside6_studio' / 'main.py')
    icon_ico = gui_root / 'pyside6_studio' / 'resources' / 'icons' / 'app_icon.ico'
    resources_dir = gui_root / 'pyside6_studio' / 'resources'
    
    cmd = [
        sys.executable, '-m', 'PyInstaller',
        '--noconfirm',
        '--name', 'ManyBodyStudio',
        '--onedir',
        '--windowed',
        '--distpath', str(gui_root / 'dist'),
        '--workpath', str(gui_root / 'build'),
        '--specpath', str(gui_root / 'build'),
        '--icon', str(icon_ico),
        '--add-data', f'{resources_dir};pyside6_studio/resources',
        '--add-data', f'{resources_dir};resources',
        '--exclude-module', 'cupy',
        '--exclude-module', 'torch',
        '--exclude-module', 'torchvision',
        '--exclude-module', 'torchaudio',
        '--collect-all', 'pyside6',
        '--collect-all', 'numba',
        '--collect-data', 'matplotlib',
        '--paths', str(project_root),
        '--paths', str(project_root / 'self_energy'),
        '--paths', str(project_root / 'self_energy' / 'solvers'),
        '--paths', str(project_root / 'susceptibility'),
        '--paths', str(gui_root / 'pyside6_studio'),
        '--hidden-import', 'self_energy',
        '--hidden-import', 'self_energy.parameters',
        '--hidden-import', 'self_energy.full_bz_solver',
        '--hidden-import', 'self_energy.sweep_core',
        '--hidden-import', 'self_energy.solvers',
        '--hidden-import', 'self_energy.solvers.cpu',
        '--hidden-import', 'self_energy.solvers.cpu.one_loop',
        '--hidden-import', 'self_energy.solvers.cpu.three_loop',
        '--hidden-import', 'solvers',
        '--hidden-import', 'solvers.cpu',
        '--hidden-import', 'solvers.cpu.one_loop',
        '--hidden-import', 'solvers.cpu.three_loop',
        '--hidden-import', 'parameters',
        '--hidden-import', 'susceptibility',
        '--hidden-import', 'susceptibility.precompute_chi0',
        '--hidden-import', 'susceptibility.sweeper',
        '--hidden-import', 'susceptibility.phase_diagram',
        '--hidden-import', 'susceptibility.solvers',
        '--hidden-import', 'susceptibility.solvers.cpu',
        '--hidden-import', 'susceptibility.solvers.cpu.ltm_solver',
        '--hidden-import', 'conductivity',
        '--hidden-import', 'pyside6_studio.core.icon_utils',
        '--hidden-import', 'pyside6_studio.backend.worker_cli',
        '--hidden-import', 'pyside6_studio.theme',
        '--hidden-import', 'pyside6_studio.canvas',
        '--hidden-import', 'pyside6_studio.widgets.interactive_mode_nav',
        entry_point
    ]

    result = subprocess.run(cmd)
    if result.returncode != 0:
        print()
        print(f'[ERROR] PyInstaller failed with exit code {result.returncode}')
        sys.exit(result.returncode)

    # 4. Initialize results and resources hierarchy
    print()
    (dist_dir / 'results' / 'plots').mkdir(parents=True, exist_ok=True)
    (dist_dir / 'results' / 'data').mkdir(parents=True, exist_ok=True)
    dist_cache = dist_dir / 'results' / 'cache'
    dist_cache.mkdir(parents=True, exist_ok=True)

    # Copy lightweight starter foundation caches (<= 20MB) into dist/results/cache
    src_cache = gui_root / 'results' / 'cache'
    if src_cache.exists():
        copied_count = 0
        for cache_file in src_cache.glob('*.npz'):
            if cache_file.stat().st_size <= 20 * 1024 * 1024:
                shutil.copy2(cache_file, dist_cache)
                copied_count += 1
        print(f'      Bundled {copied_count} foundation cache files into dist/results/cache/')
    if resources_dir.exists():
        shutil.copytree(resources_dir, dist_dir / 'resources', dirs_exist_ok=True)
        shutil.copytree(resources_dir, dist_dir / 'pyside6_studio' / 'resources', dirs_exist_ok=True)
        internal_dir = dist_dir / '_internal'
        if internal_dir.exists():
            shutil.copytree(resources_dir, internal_dir / 'resources', dirs_exist_ok=True)
            shutil.copytree(resources_dir, internal_dir / 'pyside6_studio' / 'resources', dirs_exist_ok=True)
            # Copy physics backend modules directly into _internal
            print('      Copying physics backend modules (self_energy, solvers, susceptibility, conductivity)...')
            ignore_pat = shutil.ignore_patterns('.venv', '.git', '.idea', '__pycache__', 'results', '*.pyc')
            shutil.copytree(project_root / 'self_energy', internal_dir / 'self_energy', dirs_exist_ok=True, ignore=ignore_pat)
            shutil.copytree(project_root / 'self_energy' / 'solvers', internal_dir / 'solvers', dirs_exist_ok=True, ignore=ignore_pat)
            if (project_root / 'self_energy' / 'parameters.py').exists():
                shutil.copy2(project_root / 'self_energy' / 'parameters.py', internal_dir / 'parameters.py')
            shutil.copytree(project_root / 'susceptibility', internal_dir / 'susceptibility', dirs_exist_ok=True, ignore=ignore_pat)
            shutil.copytree(project_root / 'conductivity', internal_dir / 'conductivity', dirs_exist_ok=True, ignore=ignore_pat)
            shutil.copytree(gui_root / 'pyside6_studio', internal_dir / 'pyside6_studio', dirs_exist_ok=True, ignore=ignore_pat)

    # 5. Write README
    print('[5/5] Generating distribution README...')
    readme_lines = [
        'Many-Body Studio [Beta v1 - CPU Standalone Edition]',
        '==================================================',
        '',
        'Quick Start:',
        'Double-click ManyBodyStudio.exe to launch the studio.',
        '',
        'System Requirements:',
        '- Windows 10/11 (64-bit)',
        '- Multi-core Intel or AMD CPU',
        '- No Python, PySide6, or CUDA installation required.',
        '',
        'Results and generated plots will be saved in the results folder.'
    ]
    (dist_dir / 'README.txt').write_text('\n'.join(readme_lines), encoding='utf-8')

    exe_path = dist_dir / 'ManyBodyStudio.exe'
    print()
    print('=' * 72)
    print('  BUILD SUCCESSFUL!')
    print('=' * 72)
    print(f'Standalone package: {dist_dir}')
    print(f'Executable:         {exe_path}')
    print()
    print('You can now zip the dist/ManyBodyStudio folder and share it!')
    print('=' * 72)

if __name__ == '__main__':
    main()