#!/usr/bin/env python3
"""
Zero Leaks Standalone Executable
Portable version for air-gapped environments without web server dependency
"""

import os
import sys
import json
import sqlite3
import argparse
import tempfile
import shutil
from datetime import datetime, timezone
import subprocess
import platform

# Import Zero Leaks modules
try:
    from generate_certificate import generate_certificate, COMPLIANCE_STANDARDS
    from hpa_dco_handler import HPADCOHandler
    from firmware_wiper import FirmwareLevelWiper
    from smart_analyzer import SMARTAnalyzer
    from offline_handler import OfflineHandler
except ImportError as e:
    print(f"Error importing Zero Leaks modules: {e}")
    print("Make sure all Zero Leaks files are in the same directory")
    sys.exit(1)

class ZeroLeaksStandalone:
    """Standalone Zero Leaks application for air-gapped environments"""
    
    def __init__(self):
        self.app_dir = os.path.dirname(os.path.abspath(__file__))
        self.platform_info = self._detect_platform()
        self.offline_handler = OfflineHandler()
        self.setup_environment()
        
    def _detect_platform(self):
        """Detect current platform"""
        system = platform.system()
        return {
            'system': system,
            'machine': platform.machine(),
            'release': platform.release(),
            'is_windows': system == 'Windows',
            'is_linux': system == 'Linux',
            'is_macos': system == 'Darwin'
        }
    
    def setup_environment(self):
        """Setup standalone environment"""
        
        # Create necessary directories
        dirs_to_create = ['certificates', 'logs', 'temp']
        for dir_name in dirs_to_create:
            dir_path = os.path.join(self.app_dir, dir_name)
            os.makedirs(dir_path, exist_ok=True)
        
        # Initialize offline database
        self.offline_handler.setup_offline_database()
        
        print(f"🚀 Zero Leaks Standalone v1.3 - {self.platform_info['system']}")
        print(f"📁 Working directory: {self.app_dir}")
        
    def interactive_mode(self):
        """Start interactive command-line interface"""
        
        print("\n" + "="*60)
        print("ZERO LEAKS - SECURE DATA WIPING (STANDALONE MODE)")
        print("="*60)
        print("🔒 Professional data destruction with cryptographic certificates")
        print("🌐 Air-gapped mode - No network required")
        print("📜 Full compliance: DoD 5220.22-M, NIST SP 800-88, GDPR")
        print("="*60)
        
        while True:
            print("\n📋 Available Commands:")
            print("  1. 🗂️  Browse and select files/folders")
            print("  2. 💾 List available disks")
            print("  3. 🔍 Analyze disk health (SMART)")
            print("  4. 🕵️ Detect HPA/DCO hidden areas")
            print("  5. 🧹 Wipe files/folders")
            print("  6. 🔥 Wipe entire disk")
            print("  7. 🔬 Firmware-level wipe")
            print("  8. 📜 Generate certificate")
            print("  9. ✅ Verify certificate")
            print(" 10. 📊 View offline status")
            print(" 11. ❓ Help")
            print("  0. 🚪 Exit")
            
            try:
                choice = input("\n👉 Enter your choice (0-11): ").strip()
                
                if choice == '0':
                    print("👋 Thank you for using Zero Leaks!")
                    break
                elif choice == '1':
                    self.browse_filesystem()
                elif choice == '2':
                    self.list_disks()
                elif choice == '3':
                    self.analyze_disk_health()
                elif choice == '4':
                    self.detect_hpa_dco()
                elif choice == '5':
                    self.wipe_files_folders()
                elif choice == '6':
                    self.wipe_disk()
                elif choice == '7':
                    self.firmware_wipe()
                elif choice == '8':
                    self.generate_certificate_interactive()
                elif choice == '9':
                    self.verify_certificate_interactive()
                elif choice == '10':
                    self.show_offline_status()
                elif choice == '11':
                    self.show_help()
                else:
                    print("❌ Invalid choice. Please enter a number between 0-11.")
                    
            except KeyboardInterrupt:
                print("\n\n👋 Goodbye!")
                break
            except Exception as e:
                print(f"❌ Error: {e}")
    
    def browse_filesystem(self):
        """Interactive filesystem browser"""
        
        print("\n📁 Filesystem Browser")
        print("=" * 30)
        
        if self.platform_info['is_windows']:
            # Show available drives on Windows
            drives = [f"{chr(i)}:\\" for i in range(ord('A'), ord('Z')+1) if os.path.exists(f"{chr(i)}:\\")]
            print("Available drives:")
            for i, drive in enumerate(drives, 1):
                print(f"  {i}. {drive}")
        else:
            # Show root and common mount points on Unix
            paths = ['/']
            if os.path.exists('/mnt'):
                paths.append('/mnt')
            if os.path.exists('/media'):
                paths.append('/media')
            print("Available paths:")
            for i, path in enumerate(paths, 1):
                print(f"  {i}. {path}")
        
        # Simple path input for now
        path = input("\n📁 Enter full path to browse: ").strip()
        if os.path.exists(path):
            self._list_directory_contents(path)
        else:
            print(f"❌ Path not found: {path}")
    
    def _list_directory_contents(self, path):
        """List directory contents"""
        
        try:
            items = os.listdir(path)
            print(f"\n📂 Contents of {path}:")
            
            # Separate directories and files
            dirs = [item for item in items if os.path.isdir(os.path.join(path, item))]
            files = [item for item in items if os.path.isfile(os.path.join(path, item))]
            
            # Show directories first
            for directory in sorted(dirs):
                print(f"  📁 {directory}/")
            
            # Then files
            for file in sorted(files):
                file_path = os.path.join(path, file)
                try:
                    size = os.path.getsize(file_path)
                    size_str = self._format_size(size)
                    print(f"  📄 {file} ({size_str})")
                except:
                    print(f"  📄 {file}")
                    
        except PermissionError:
            print(f"❌ Permission denied: {path}")
        except Exception as e:
            print(f"❌ Error listing directory: {e}")
    
    def list_disks(self):
        """List available disks for wiping"""
        
        print("\n💾 Available Disks")
        print("=" * 30)
        
        if self.platform_info['is_windows']:
            self._list_windows_disks()
        elif self.platform_info['is_linux']:
            self._list_linux_disks()
        else:
            print("❌ Disk listing not supported on this platform")
    
    def _list_windows_disks(self):
        """List Windows disks using WMI"""
        
        try:
            cmd = 'wmic diskdrive get DeviceID,Size,Model /format:csv'
            result = subprocess.run(cmd, capture_output=True, text=True, shell=True,
                                  creationflags=subprocess.CREATE_NO_WINDOW)
            
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                for line in lines[1:]:  # Skip header
                    if line.strip():
                        parts = line.split(',')
                        if len(parts) >= 4:
                            device_id = parts[1].strip()
                            model = parts[2].strip()
                            size = parts[3].strip()
                            
                            try:
                                size_gb = int(size) / (1024**3)
                                print(f"  🖥️  {device_id}: {model} ({size_gb:.1f} GB)")
                            except:
                                print(f"  🖥️  {device_id}: {model}")
            else:
                print("❌ Failed to list Windows disks")
                
        except Exception as e:
            print(f"❌ Error listing Windows disks: {e}")
    
    def _list_linux_disks(self):
        """List Linux disks using lsblk"""
        
        try:
            cmd = ['lsblk', '-d', '-o', 'NAME,SIZE,MODEL,TYPE']
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                for line in lines[1:]:  # Skip header
                    parts = line.split()
                    if len(parts) >= 3 and parts[-1] == 'disk':
                        name = f"/dev/{parts[0]}"
                        size = parts[1] if len(parts) > 1 else "Unknown"
                        model = ' '.join(parts[2:-1]) if len(parts) > 3 else "Unknown"
                        print(f"  🖥️  {name}: {model} ({size})")
            else:
                print("❌ Failed to list Linux disks")
                
        except Exception as e:
            print(f"❌ Error listing Linux disks: {e}")
    
    def analyze_disk_health(self):
        """Analyze disk health using SMART data"""
        
        print("\n🔍 Disk Health Analysis")
        print("=" * 30)
        
        disk_path = input("💾 Enter disk path (e.g., /dev/sda or \\\\.\\PhysicalDrive0): ").strip()
        
        if not disk_path:
            print("❌ No disk path provided")
            return
        
        try:
            analyzer = SMARTAnalyzer()
            print(f"🔍 Analyzing {disk_path}...")
            
            analysis = analyzer.comprehensive_disk_analysis(disk_path)
            
            # Display summary
            print(f"\n📋 Analysis Results:")
            print(f"  🏥 Health Status: {analysis.get('health_status', 'Unknown')}")
            print(f"  📊 Health Score: {analysis.get('health_score', 'N/A')}/100")
            
            basic_info = analysis.get('basic_info', {})
            if basic_info:
                print(f"  💾 Drive Type: {basic_info.get('drive_type', 'Unknown')}")
                print(f"  🏷️  Model: {basic_info.get('model_name', 'Unknown')}")
            
            # Show warnings
            warnings = analysis.get('warnings', [])
            if warnings:
                print(f"\n⚠️  Warnings:")
                for warning in warnings:
                    print(f"    ⚠️  {warning}")
            
            # Show recommendations
            recommendations = analysis.get('recommendations', [])
            if recommendations:
                print(f"\n💡 Recommendations:")
                for rec in recommendations:
                    print(f"    💡 {rec}")
            
            # Save detailed analysis
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"disk_analysis_{timestamp}.json"
            filepath = os.path.join(self.app_dir, 'logs', filename)
            
            with open(filepath, 'w') as f:
                json.dump(analysis, f, indent=2)
            
            print(f"\n📄 Detailed analysis saved to: {filepath}")
            
        except Exception as e:
            print(f"❌ Analysis failed: {e}")
    
    def detect_hpa_dco(self):
        """Detect HPA/DCO hidden areas"""
        
        print("\n🕵️ HPA/DCO Detection")
        print("=" * 30)
        
        disk_path = input("💾 Enter disk path: ").strip()
        
        if not disk_path:
            print("❌ No disk path provided")
            return
        
        try:
            handler = HPADCOHandler()
            print(f"🔍 Scanning {disk_path} for hidden areas...")
            
            results = handler.detect_hpa_dco(disk_path)
            
            print(f"\n📋 Detection Results:")
            print(f"  🔍 HPA Detected: {'Yes' if results['hpa_detected'] else 'No'}")
            print(f"  🔍 DCO Detected: {'Yes' if results['dco_detected'] else 'No'}")
            
            if results['hidden_capacity'] > 0:
                hidden_gb = (results['hidden_capacity'] * 512) / (1024**3)
                print(f"  📏 Hidden Capacity: {hidden_gb:.2f} GB")
            
            if results['warnings']:
                print(f"\n⚠️  Warnings:")
                for warning in results['warnings']:
                    print(f"    ⚠️  {warning}")
            
            # Generate report
            report = handler.generate_hpa_dco_report(disk_path)
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"hpa_dco_report_{timestamp}.json"
            filepath = os.path.join(self.app_dir, 'logs', filename)
            
            with open(filepath, 'w') as f:
                json.dump(report, f, indent=2)
            
            print(f"\n📄 Report saved to: {filepath}")
            
        except Exception as e:
            print(f"❌ HPA/DCO detection failed: {e}")
    
    def wipe_files_folders(self):
        """Wipe files or folders"""
        
        print("\n🧹 File/Folder Wiping")
        print("=" * 30)
        
        target_path = input("📁 Enter file or folder path to wipe: ").strip()
        
        if not target_path or not os.path.exists(target_path):
            print("❌ Invalid or non-existent path")
            return
        
        # Show available methods
        print("\n🔐 Available Wiping Methods:")
        methods = {
            '1': ('zeros', 'Single Pass Zero (NIST Clear)'),
            '2': ('dod', 'DoD 5220.22-M (3-pass)'),
            '3': ('dod_7pass', 'DoD ECE (7-pass)'),
            '4': ('gutmann', 'Gutmann (35-pass)'),
            '5': ('random', 'Random Data (1-pass)')
        }
        
        for key, (method, desc) in methods.items():
            print(f"  {key}. {desc}")
        
        method_choice = input("\n👉 Select method (1-5): ").strip()
        
        if method_choice not in methods:
            print("❌ Invalid method selection")
            return
        
        wipe_method, method_desc = methods[method_choice]
        
        # Confirmation
        print(f"\n⚠️  WARNING: This will permanently destroy all data!")
        print(f"📁 Target: {target_path}")
        print(f"🔐 Method: {method_desc}")
        
        confirm = input("\n❓ Type 'WIPE' to confirm: ").strip()
        
        if confirm != 'WIPE':
            print("❌ Operation cancelled")
            return
        
        self._perform_wipe(target_path, wipe_method, 'file' if os.path.isfile(target_path) else 'folder')
    
    def wipe_disk(self):
        """Wipe entire disk"""
        
        print("\n🔥 Disk Wiping")
        print("=" * 30)
        print("⚠️  WARNING: THIS WILL DESTROY ALL DATA ON THE DISK!")
        
        disk_path = input("💾 Enter disk path: ").strip()
        
        if not disk_path:
            print("❌ No disk path provided")
            return
        
        # Show available methods (same as files)
        print("\n🔐 Available Wiping Methods:")
        methods = {
            '1': ('zeros', 'Single Pass Zero (NIST Clear)'),
            '2': ('dod', 'DoD 5220.22-M (3-pass)'),
            '3': ('dod_7pass', 'DoD ECE (7-pass)'),
            '4': ('gutmann', 'Gutmann (35-pass)'),
            '5': ('random', 'Random Data (1-pass)'),
            '6': ('ata_secure_erase', 'ATA Secure Erase (Hardware)')
        }
        
        for key, (method, desc) in methods.items():
            print(f"  {key}. {desc}")
        
        method_choice = input("\n👉 Select method (1-6): ").strip()
        
        if method_choice not in methods:
            print("❌ Invalid method selection")
            return
        
        wipe_method, method_desc = methods[method_choice]
        
        # Final confirmation
        print(f"\n🚨 FINAL WARNING: ENTIRE DISK WILL BE WIPED!")
        print(f"💾 Disk: {disk_path}")
        print(f"🔐 Method: {method_desc}")
        print(f"⚠️  ALL DATA WILL BE PERMANENTLY LOST!")
        
        confirm1 = input("\n❓ Type 'DESTROY' to continue: ").strip()
        
        if confirm1 != 'DESTROY':
            print("❌ Operation cancelled")
            return
        
        confirm2 = input("❓ Type 'CONFIRM' to proceed: ").strip()
        
        if confirm2 != 'CONFIRM':
            print("❌ Operation cancelled")
            return
        
        self._perform_wipe(disk_path, wipe_method, 'disk')
    
    def firmware_wipe(self):
        """Perform firmware-level wipe"""
        
        print("\n🔬 Firmware-Level Wiping")
        print("=" * 30)
        print("⚠️  WARNING: ADVANCED OPERATION - CAN BRICK DRIVES!")
        
        disk_path = input("💾 Enter disk path: ").strip()
        
        if not disk_path:
            print("❌ No disk path provided")
            return
        
        try:
            wiper = FirmwareLevelWiper()
            
            # Analyze drive first
            print("🔍 Analyzing drive capabilities...")
            analysis = wiper.analyze_drive_capabilities(disk_path)
            
            print(f"\n📋 Drive Analysis:")
            print(f"  💾 Drive Type: {analysis['drive_type']}")
            print(f"  🔌 Interface: {analysis['interface']}")
            print(f"  🔐 ATA Secure Erase: {'Yes' if analysis['supports_ata_secure_erase'] else 'No'}")
            print(f"  💾 NVMe Format: {'Yes' if analysis['supports_nvme_format'] else 'No'}")
            
            if analysis['warnings']:
                print(f"\n⚠️  Warnings:")
                for warning in analysis['warnings']:
                    print(f"    ⚠️  {warning}")
            
            # Final confirmation
            print(f"\n🚨 EXTREME WARNING: FIRMWARE OPERATIONS CAN BRICK THE DRIVE!")
            confirm = input("❓ Type 'FIRMWARE_WIPE' to proceed: ").strip()
            
            if confirm != 'FIRMWARE_WIPE':
                print("❌ Operation cancelled")
                return
            
            print("🔬 Performing firmware-level wipe...")
            result = wiper.perform_firmware_wipe(disk_path, 'auto', force=True)
            
            if result['success']:
                print("✅ Firmware wipe completed successfully!")
            else:
                print("❌ Firmware wipe failed:")
                for error in result['errors']:
                    print(f"    ❌ {error}")
            
        except Exception as e:
            print(f"❌ Firmware wipe failed: {e}")
    
    def _perform_wipe(self, target_path, wipe_method, wipe_type):
        """Perform the actual wipe operation"""
        
        print(f"\n🔄 Starting wipe operation...")
        print(f"📁 Target: {target_path}")
        print(f"🔐 Method: {wipe_method}")
        
        # Create log file
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        log_filename = f"wipe_log_{timestamp}.txt"
        log_filepath = os.path.join(self.app_dir, 'logs', log_filename)
        
        try:
            # Determine C executable path
            if self.platform_info['is_windows']:
                executable_name = "wipeEngine.exe"
            else:
                executable_name = "wipeEngine"
            
            c_executable = os.path.join(self.app_dir, 'wipingEngine', executable_name)
            
            if not os.path.exists(c_executable):
                print(f"❌ Wipe engine not found: {c_executable}")
                print("Please ensure wipeEngine is compiled and available")
                return
            
            # Execute wiping command
            command = [c_executable, f'--{wipe_type}', target_path, wipe_method]
            
            print("🔄 Wiping in progress... This may take a long time.")
            
            with open(log_filepath, 'w') as log_file:
                # Write log header
                log_file.write("=== Zero Leaks Standalone Wipe Log ===\n")
                log_file.write(f"Timestamp: {datetime.now().isoformat()}\n")
                log_file.write(f"Target: {target_path}\n")
                log_file.write(f"Method: {wipe_method}\n")
                log_file.write(f"Type: {wipe_type}\n")
                log_file.write("=== Wipe Output ===\n")
                log_file.flush()
                
                # Run wipe process
                process = subprocess.run(command, capture_output=True, text=True, timeout=7200)  # 2 hours max
                
                # Write output to log
                log_file.write(process.stdout)
                log_file.write(process.stderr)
                log_file.write(f"\n=== Exit Code: {process.returncode} ===\n")
            
            if process.returncode == 0:
                print("✅ Wipe completed successfully!")
                
                # Generate certificate in offline mode
                try:
                    print("📜 Generating certificate...")
                    
                    wipe_details = {
                        'wipe_method': wipe_method,
                        'asset_serial': 'N/A',
                        'start_time': datetime.now(timezone.utc).isoformat(),
                        'end_time': datetime.now(timezone.utc).isoformat(),
                        'wipe_result': 'Success',
                        'technician': 'Standalone User',
                        'witness': 'Not Specified',
                        'asset_type': wipe_type.capitalize()
                    }
                    
                    cert_json, cert_pdf, cert_id = self.offline_handler.generate_offline_certificate(
                        log_filepath, target_path, self.platform_info, wipe_details
                    )
                    
                    print(f"📜 Certificate generated: {cert_json}")
                    print(f"📄 PDF certificate: {cert_pdf}")
                    print(f"🆔 Certificate ID: {cert_id}")
                    
                except Exception as cert_error:
                    print(f"⚠️  Certificate generation failed: {cert_error}")
                    print("Wipe completed but certificate could not be generated")
            else:
                print(f"❌ Wipe failed with exit code: {process.returncode}")
                print("Check the log file for details")
            
            print(f"📄 Log saved to: {log_filepath}")
            
        except subprocess.TimeoutExpired:
            print("❌ Wipe operation timed out (2 hours)")
        except Exception as e:
            print(f"❌ Wipe operation failed: {e}")
    
    def generate_certificate_interactive(self):
        """Interactive certificate generation"""
        
        print("\n📜 Certificate Generation")
        print("=" * 30)
        
        log_file = input("📄 Enter wipe log file path: ").strip()
        
        if not log_file or not os.path.exists(log_file):
            print("❌ Invalid or non-existent log file")
            return
        
        target = input("📁 Enter wiped target path: ").strip()
        
        try:
            print("📜 Generating certificate...")
            
            wipe_details = {
                'wipe_method': 'manual',
                'asset_serial': 'N/A',
                'start_time': datetime.now(timezone.utc).isoformat(),
                'end_time': datetime.now(timezone.utc).isoformat(),
                'wipe_result': 'Success',
                'technician': input("👤 Technician name: ").strip() or 'Unknown',
                'witness': input("👁️  Witness name (optional): ").strip() or 'Not Specified',
                'asset_type': 'Manual'
            }
            
            cert_json, cert_pdf = generate_certificate(log_file, target, self.platform_info, wipe_details)
            
            print(f"✅ Certificate generated successfully!")
            print(f"📜 JSON: {cert_json}")
            print(f"📄 PDF: {cert_pdf}")
            
        except Exception as e:
            print(f"❌ Certificate generation failed: {e}")
    
    def verify_certificate_interactive(self):
        """Interactive certificate verification"""
        
        print("\n✅ Certificate Verification")
        print("=" * 30)
        
        cert_file = input("📜 Enter certificate JSON file path: ").strip()
        
        if not cert_file or not os.path.exists(cert_file):
            print("❌ Invalid or non-existent certificate file")
            return
        
        try:
            from generate_certificate import verify_certificate_authenticity
            
            print("🔍 Verifying certificate...")
            is_valid, message = verify_certificate_authenticity(cert_file)
            
            if is_valid:
                print(f"✅ Certificate is VALID")
                print(f"📋 {message}")
            else:
                print(f"❌ Certificate is INVALID")
                print(f"📋 {message}")
                
        except Exception as e:
            print(f"❌ Certificate verification failed: {e}")
    
    def show_offline_status(self):
        """Show offline mode status"""
        
        print("\n📊 Offline Status")
        print("=" * 30)
        
        status = self.offline_handler.get_offline_status()
        
        print(f"🌐 Network Status: {'Online' if status['online'] else 'Offline'}")
        print(f"📊 Total Pending Operations: {status['total_pending']}")
        
        if status['certificates']:
            print(f"\n📜 Certificates:")
            for cert_status, count in status['certificates'].items():
                print(f"  {cert_status.title()}: {count}")
        
        if status['operations']:
            print(f"\n⚙️  Operations:")
            for op_status, count in status['operations'].items():
                print(f"  {op_status.title()}: {count}")
    
    def show_help(self):
        """Show help information"""
        
        print("\n❓ Zero Leaks Standalone Help")
        print("=" * 40)
        
        help_text = """
🎯 PURPOSE:
Zero Leaks provides military-grade secure data wiping with cryptographic
certificates for compliance and verification. This standalone version
works in air-gapped environments without network connectivity.

🔐 WIPING METHODS:
• Single Pass Zero: Fast, suitable for non-sensitive data
• DoD 5220.22-M (3-pass): Government standard for classified data  
• DoD ECE (7-pass): Enhanced security for top secret data
• Gutmann (35-pass): Maximum security for legacy magnetic drives
• Random Data: Cryptographically secure random overwrite
• ATA Secure Erase: Hardware-based SSD wiping

🏥 DISK ANALYSIS:
• SMART health monitoring and diagnostics
• HPA/DCO hidden area detection
• Firmware capability assessment
• Erasure coverage verification

📜 CERTIFICATES:
• Cryptographically signed with RSA-2048
• PDF and JSON formats for human/machine use
• QR codes for quick verification
• Offline generation with delayed sync

⚠️  SAFETY WARNINGS:
• All wiping operations are IRREVERSIBLE
• Always backup important data first
• Firmware operations can brick drives
• Use appropriate method for your security needs

🆘 SUPPORT:
For technical support or questions, consult the README.md file
or visit the Zero Leaks documentation.
        """
        
        print(help_text)
    
    def _format_size(self, size_bytes):
        """Format size in human-readable format"""
        
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} PB"

def main():
    """Main entry point for standalone application"""
    
    parser = argparse.ArgumentParser(
        description='Zero Leaks Standalone - Secure Data Wiping for Air-Gapped Environments',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Interactive mode (recommended)
  python standalone.py
  
  # Command-line wipe
  python standalone.py wipe --file /path/to/file --method dod
  
  # Disk analysis
  python standalone.py analyze --disk /dev/sda
        """
    )
    
    parser.add_argument('command', nargs='?', default='interactive',
                       choices=['interactive', 'wipe', 'analyze', 'detect', 'help'],
                       help='Command to execute (default: interactive)')
    
    parser.add_argument('--file', help='File or folder to wipe')
    parser.add_argument('--disk', help='Disk to analyze or wipe')
    parser.add_argument('--method', choices=['zeros', 'dod', 'dod_7pass', 'gutmann', 'random', 'ata_secure_erase'],
                       default='dod', help='Wiping method')
    parser.add_argument('--force', action='store_true', help='Force destructive operations')
    
    args = parser.parse_args()
    
    app = ZeroLeaksStandalone()
    
    if args.command == 'interactive' or args.command is None:
        app.interactive_mode()
        
    elif args.command == 'wipe':
        if not args.file and not args.disk:
            print("Error: --file or --disk required for wipe command")
            sys.exit(1)
        
        if not args.force:
            print("Error: --force flag required for destructive operations")
            sys.exit(1)
        
        target = args.file or args.disk
        wipe_type = 'disk' if args.disk else ('file' if os.path.isfile(target) else 'folder')
        
        app._perform_wipe(target, args.method, wipe_type)
        
    elif args.command == 'analyze':
        if not args.disk:
            print("Error: --disk required for analyze command")
            sys.exit(1)
        
        analyzer = SMARTAnalyzer()
        analysis = analyzer.comprehensive_disk_analysis(args.disk)
        print(json.dumps(analysis, indent=2))
        
    elif args.command == 'detect':
        if not args.disk:
            print("Error: --disk required for detect command")
            sys.exit(1)
        
        handler = HPADCOHandler()
        results = handler.detect_hpa_dco(args.disk)
        print(json.dumps(results, indent=2))
        
    elif args.command == 'help':
        app.show_help()

if __name__ == '__main__':
    main()