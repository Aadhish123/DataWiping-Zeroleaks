#!/usr/bin/env python3
"""
Bootable Media Generator for Zero Leaks
Creates bootable USB/ISO with offline data wiping capability
"""

import os
import subprocess
import tempfile
import shutil
import platform
import json
from datetime import datetime

class BootableMediaGenerator:
    """Generate bootable USB/ISO with Zero Leaks wiping tools"""
    
    def __init__(self):
        self.platform_info = self._detect_platform()
        self.temp_dir = None
        self.iso_dir = None
        
    def _detect_platform(self):
        """Detect current platform"""
        system = platform.system()
        return {
            'system': system,
            'is_windows': system == 'Windows',
            'is_linux': system == 'Linux',
            'is_macos': system == 'Darwin'
        }
    
    def create_bootable_iso(self, output_path, include_gui=True):
        """
        Create bootable ISO with Zero Leaks tools
        
        Args:
            output_path: Path where ISO will be created
            include_gui: Whether to include web-based GUI
        """
        print(f"Creating bootable ISO: {output_path}")
        
        # Create temporary directory structure
        self.temp_dir = tempfile.mkdtemp(prefix='zeroleaks_')
        self.iso_dir = os.path.join(self.temp_dir, 'zeroleaks-live')
        
        try:
            # Create directory structure
            self._create_iso_structure()
            
            # Copy Zero Leaks files
            self._copy_zeroleaks_files()
            
            # Create bootable components
            self._create_bootable_components(include_gui)
            
            # Generate the ISO
            self._generate_iso(output_path)
            
            print(f"✅ Bootable ISO created successfully: {output_path}")
            return True
            
        except Exception as e:
            print(f"❌ Error creating bootable ISO: {e}")
            return False
        finally:
            # Cleanup
            if self.temp_dir and os.path.exists(self.temp_dir):
                shutil.rmtree(self.temp_dir)
    
    def _create_iso_structure(self):
        """Create the directory structure for the ISO"""
        dirs_to_create = [
            'boot',
            'boot/grub',
            'live',
            'zeroleaks',
            'zeroleaks/bin',
            'zeroleaks/certs',
            'zeroleaks/logs',
            'zeroleaks/web',
            'scripts'
        ]
        
        for dir_path in dirs_to_create:
            full_path = os.path.join(self.iso_dir, dir_path)
            os.makedirs(full_path, exist_ok=True)
            print(f"Created directory: {dir_path}")
    
    def _copy_zeroleaks_files(self):
        """Copy Zero Leaks application files to ISO"""
        source_files = {
            # Core wiping engine
            'wipingEngine/wipeEngine.c': 'zeroleaks/bin/wipeEngine.c',
            'wipingEngine/wipeEngine': 'zeroleaks/bin/wipeEngine',
            
            # Python modules
            'generate_certificate.py': 'zeroleaks/generate_certificate.py',
            'hpa_dco_handler.py': 'zeroleaks/hpa_dco_handler.py',
            'database.py': 'zeroleaks/database.py',
            
            # Signing keys
            'signing_key.pem': 'zeroleaks/signing_key.pem',
            'signing_pub.pem': 'zeroleaks/signing_pub.pem',
            
            # Web interface (if including GUI)
            'app.py': 'zeroleaks/web/app.py',
            'templates': 'zeroleaks/web/templates',
            'static': 'zeroleaks/web/static'
        }
        
        for src, dst in source_files.items():
            src_path = src
            dst_path = os.path.join(self.iso_dir, dst)
            
            try:
                if os.path.exists(src_path):
                    if os.path.isfile(src_path):
                        # Copy file
                        os.makedirs(os.path.dirname(dst_path), exist_ok=True)
                        shutil.copy2(src_path, dst_path)
                        print(f"Copied: {src} -> {dst}")
                    elif os.path.isdir(src_path):
                        # Copy directory
                        shutil.copytree(src_path, dst_path, dirs_exist_ok=True)
                        print(f"Copied directory: {src} -> {dst}")
                else:
                    print(f"Warning: Source file not found: {src}")
            except Exception as e:
                print(f"Error copying {src}: {e}")
    
    def _create_bootable_components(self, include_gui):
        """Create bootable components (GRUB, init scripts, etc.)"""
        
        # Create GRUB configuration
        grub_cfg = """
set timeout=10
set default=0

menuentry "Zero Leaks - Secure Data Wiper" {
    linux /boot/vmlinuz boot=live components quiet splash
    initrd /boot/initrd.img
}

menuentry "Zero Leaks - Safe Mode" {
    linux /boot/vmlinuz boot=live components quiet splash nomodeset
    initrd /boot/initrd.img
}

menuentry "Memory Test (memtest86+)" {
    linux16 /boot/memtest86+.bin
}
"""
        
        grub_path = os.path.join(self.iso_dir, 'boot/grub/grub.cfg')
        with open(grub_path, 'w') as f:
            f.write(grub_cfg)
        
        # Create init script for Zero Leaks
        init_script = """#!/bin/bash
# Zero Leaks Boot Script

echo "Starting Zero Leaks Secure Data Wiper..."

# Mount essential filesystems
mount -t proc proc /proc
mount -t sysfs sysfs /sys
mount -t devtmpfs devtmpfs /dev

# Load necessary kernel modules
modprobe ahci
modprobe libata
modprobe scsi_mod

# Setup networking (for certificate validation)
dhclient eth0 2>/dev/null || true

# Start Zero Leaks services
cd /zeroleaks

# Compile wiping engine if needed
if [ ! -f "bin/wipeEngine" ]; then
    echo "Compiling wiping engine..."
    gcc -o bin/wipeEngine bin/wipeEngine.c -lpthread
fi

# Make executable
chmod +x bin/wipeEngine

# Check for HPA/DCO detection tools
if ! command -v hdparm &> /dev/null; then
    echo "Warning: hdparm not available - HPA/DCO detection limited"
fi

# Start web interface if requested
if [ "$1" == "--gui" ]; then
    echo "Starting web interface on port 8080..."
    cd web && python3 app.py --port 8080 &
    echo "Access Zero Leaks at: http://localhost:8080"
fi

# Start interactive mode
echo "==================================="
echo "Zero Leaks Secure Data Wiper v1.3"
echo "==================================="
echo ""
echo "Available commands:"
echo "  zeroleaks-gui    - Start web interface"
echo "  zeroleaks-wipe   - Command line wiping"
echo "  zeroleaks-detect - Detect HPA/DCO"
echo "  zeroleaks-cert   - Generate certificate"
echo ""

# Create command aliases
alias zeroleaks-gui='cd /zeroleaks/web && python3 app.py --port 8080'
alias zeroleaks-wipe='/zeroleaks/bin/wipeEngine'
alias zeroleaks-detect='python3 /zeroleaks/hpa_dco_handler.py'
alias zeroleaks-cert='python3 /zeroleaks/generate_certificate.py'

# Start shell
/bin/bash
"""
        
        init_path = os.path.join(self.iso_dir, 'scripts/init-zeroleaks')
        with open(init_path, 'w') as f:
            f.write(init_script)
        os.chmod(init_path, 0o755)
        
        # Create info file
        info = {
            'name': 'Zero Leaks Bootable Media',
            'version': '1.3',
            'created': datetime.now().isoformat(),
            'platform': 'Linux x86_64',
            'features': [
                'Secure data wiping (6 methods)',
                'HPA/DCO detection and erasure',
                'Certificate generation',
                'Web-based GUI (optional)',
                'Command line tools',
                'Offline operation'
            ]
        }
        
        info_path = os.path.join(self.iso_dir, 'zeroleaks/info.json')
        with open(info_path, 'w') as f:
            json.dump(info, f, indent=2)
    
    def _generate_iso(self, output_path):
        """Generate the actual ISO file"""
        
        if self.platform_info['is_linux']:
            self._generate_iso_linux(output_path)
        elif self.platform_info['is_windows']:
            self._generate_iso_windows(output_path)
        else:
            raise Exception("ISO generation not supported on this platform")
    
    def _generate_iso_linux(self, output_path):
        """Generate ISO on Linux using genisoimage/mkisofs"""
        
        # Try different tools
        iso_tools = ['genisoimage', 'mkisofs', 'xorriso']
        iso_tool = None
        
        for tool in iso_tools:
            try:
                subprocess.run([tool, '--version'], capture_output=True, check=True)
                iso_tool = tool
                break
            except (subprocess.CalledProcessError, FileNotFoundError):
                continue
        
        if not iso_tool:
            raise Exception(f"No ISO creation tool found. Install one of: {', '.join(iso_tools)}")
        
        # Create ISO
        cmd = [
            iso_tool,
            '-o', output_path,
            '-b', 'boot/grub/grub.cfg',
            '-c', 'boot/boot.catalog',
            '-no-emul-boot',
            '-boot-load-size', '4',
            '-boot-info-table',
            '-J', '-R', '-V', 'ZEROLEAKS',
            self.iso_dir
        ]
        
        print(f"Creating ISO with: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            raise Exception(f"ISO creation failed: {result.stderr}")
    
    def _generate_iso_windows(self, output_path):
        """Generate ISO on Windows (requires external tools)"""
        
        # Check for CDRTools or similar
        tools = ['mkisofs.exe', 'genisoimage.exe']
        
        for tool in tools:
            tool_path = shutil.which(tool)
            if tool_path:
                cmd = [
                    tool_path,
                    '-o', output_path,
                    '-J', '-R', '-V', 'ZEROLEAKS',
                    self.iso_dir
                ]
                
                result = subprocess.run(cmd, capture_output=True, text=True)
                if result.returncode == 0:
                    return
                else:
                    raise Exception(f"ISO creation failed: {result.stderr}")
        
        raise Exception("No ISO creation tool found on Windows. Install CDRTools or similar.")
    
    def create_usb_installer(self, usb_device, iso_path):
        """Create bootable USB from ISO"""
        
        if not os.path.exists(iso_path):
            raise Exception(f"ISO file not found: {iso_path}")
        
        if self.platform_info['is_linux']:
            return self._create_usb_linux(usb_device, iso_path)
        else:
            raise Exception("USB creation only supported on Linux")
    
    def _create_usb_linux(self, usb_device, iso_path):
        """Create bootable USB on Linux using dd"""
        
        print(f"WARNING: This will erase all data on {usb_device}")
        print("Make sure this is the correct device!")
        
        confirm = input(f"Type 'CREATE_USB' to write to {usb_device}: ")
        if confirm != 'CREATE_USB':
            print("USB creation cancelled")
            return False
        
        # Use dd to write ISO to USB
        cmd = ['dd', f'if={iso_path}', f'of={usb_device}', 'bs=4M', 'status=progress']
        
        try:
            print(f"Writing ISO to USB device: {' '.join(cmd)}")
            result = subprocess.run(cmd, check=True)
            
            # Sync to ensure write completion
            subprocess.run(['sync'], check=True)
            
            print("✅ Bootable USB created successfully!")
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"❌ USB creation failed: {e}")
            return False

def main():
    """Command line interface for bootable media generator"""
    
    import argparse
    
    parser = argparse.ArgumentParser(description='Zero Leaks Bootable Media Generator')
    parser.add_argument('command', choices=['iso', 'usb'], help='Create ISO or USB')
    parser.add_argument('output', help='Output path for ISO or USB device')
    parser.add_argument('--no-gui', action='store_true', help='Exclude web GUI')
    parser.add_argument('--iso-path', help='ISO path for USB creation')
    
    args = parser.parse_args()
    
    generator = BootableMediaGenerator()
    
    if args.command == 'iso':
        success = generator.create_bootable_iso(args.output, include_gui=not args.no_gui)
        exit(0 if success else 1)
        
    elif args.command == 'usb':
        if not args.iso_path:
            print("Error: --iso-path required for USB creation")
            exit(1)
        success = generator.create_usb_installer(args.output, args.iso_path)
        exit(0 if success else 1)

if __name__ == '__main__':
    main()