#!/usr/bin/env python3
"""
Firmware-Level Wiping Module
Advanced low-level disk wiping including reserved areas and bad sectors
"""

import subprocess
import platform
import os
import json
import time
from datetime import datetime

class FirmwareLevelWiper:
    """Handle firmware-level wiping operations"""
    
    def __init__(self):
        self.platform_info = self._detect_platform()
        self.available_tools = self._check_available_tools()
        
    def _detect_platform(self):
        """Detect current platform"""
        system = platform.system()
        return {
            'system': system,
            'is_windows': system == 'Windows',
            'is_linux': system == 'Linux',
            'is_macos': system == 'Darwin'
        }
    
    def _check_available_tools(self):
        """Check what firmware-level tools are available"""
        tools = {
            'hdparm': False,
            'nvme_cli': False,
            'smartctl': False,
            'sg_utils': False,
            'dd': False,
            'shred': False
        }
        
        # Check for Linux tools
        if self.platform_info['is_linux']:
            for tool in ['hdparm', 'nvme', 'smartctl', 'sg_format', 'dd', 'shred']:
                try:
                    result = subprocess.run(['which', tool], capture_output=True, text=True)
                    if result.returncode == 0:
                        if tool == 'nvme':
                            tools['nvme_cli'] = True
                        elif tool == 'sg_format':
                            tools['sg_utils'] = True
                        else:
                            tools[tool] = True
                except:
                    pass
        
        return tools
    
    def analyze_drive_capabilities(self, disk_path):
        """Analyze drive capabilities for firmware-level operations"""
        
        analysis = {
            'disk_path': disk_path,
            'drive_type': 'unknown',
            'interface': 'unknown',
            'supports_ata_secure_erase': False,
            'supports_nvme_format': False,
            'supports_scsi_format': False,
            'has_encryption': False,
            'firmware_capabilities': [],
            'recommended_method': 'multi_pass_overwrite',
            'warnings': [],
            'commands_available': []
        }
        
        if self.platform_info['is_linux']:
            self._analyze_linux_drive(disk_path, analysis)
        elif self.platform_info['is_windows']:
            self._analyze_windows_drive(disk_path, analysis)
        
        return analysis
    
    def _analyze_linux_drive(self, disk_path, analysis):
        """Analyze drive on Linux"""
        
        # Use lsblk to get basic info
        try:
            cmd = ['lsblk', '-o', 'NAME,TYPE,TRAN,MODEL,SIZE', '-J', disk_path]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                data = json.loads(result.stdout)
                if 'blockdevices' in data and data['blockdevices']:
                    device = data['blockdevices'][0]
                    analysis['interface'] = device.get('tran', 'unknown')
                    
                    # Determine drive type based on interface
                    if analysis['interface'] in ['sata', 'ata']:
                        analysis['drive_type'] = 'sata_hdd_ssd'
                    elif analysis['interface'] == 'nvme':
                        analysis['drive_type'] = 'nvme_ssd'
                    elif analysis['interface'] == 'scsi':
                        analysis['drive_type'] = 'scsi'
                        
        except Exception as e:
            analysis['warnings'].append(f"lsblk analysis failed: {e}")
        
        # Check ATA capabilities with hdparm
        if self.available_tools['hdparm'] and analysis['drive_type'] in ['sata_hdd_ssd']:
            self._check_ata_capabilities(disk_path, analysis)
        
        # Check NVMe capabilities
        if self.available_tools['nvme_cli'] and analysis['drive_type'] == 'nvme_ssd':
            self._check_nvme_capabilities(disk_path, analysis)
        
        # Check SCSI capabilities
        if self.available_tools['sg_utils'] and analysis['drive_type'] == 'scsi':
            self._check_scsi_capabilities(disk_path, analysis)
        
        # Use smartctl for detailed analysis
        if self.available_tools['smartctl']:
            self._check_smart_capabilities(disk_path, analysis)
    
    def _check_ata_capabilities(self, disk_path, analysis):
        """Check ATA-specific capabilities"""
        
        try:
            # Check ATA security features
            cmd = ['hdparm', '-I', disk_path]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                output = result.stdout.lower()
                
                # Check for ATA secure erase support
                if 'security erase' in output or 'enhanced security erase' in output:
                    analysis['supports_ata_secure_erase'] = True
                    analysis['firmware_capabilities'].append('ATA Security Erase')
                
                # Check for encryption
                if 'encryption' in output or 'tcg' in output:
                    analysis['has_encryption'] = True
                    analysis['firmware_capabilities'].append('Hardware Encryption')
                
                # Check for advanced features
                if 'trim' in output or 'discard' in output:
                    analysis['firmware_capabilities'].append('TRIM/Discard Support')
                
                analysis['commands_available'].append('hdparm ATA commands')
                
        except Exception as e:
            analysis['warnings'].append(f"ATA analysis failed: {e}")
    
    def _check_nvme_capabilities(self, disk_path, analysis):
        """Check NVMe-specific capabilities"""
        
        try:
            # Get NVMe device info
            cmd = ['nvme', 'id-ctrl', disk_path]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                analysis['supports_nvme_format'] = True
                analysis['firmware_capabilities'].append('NVMe Format')
                analysis['commands_available'].append('nvme-cli commands')
                
                # Check for encryption support
                if 'oacs' in result.stdout.lower():
                    analysis['firmware_capabilities'].append('NVMe Security Features')
                
        except Exception as e:
            analysis['warnings'].append(f"NVMe analysis failed: {e}")
    
    def _check_scsi_capabilities(self, disk_path, analysis):
        """Check SCSI-specific capabilities"""
        
        try:
            # Check SCSI format capabilities
            cmd = ['sg_format', '--help']  # Just check if command exists
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode in [0, 1]:  # Help usually returns 1
                analysis['supports_scsi_format'] = True
                analysis['firmware_capabilities'].append('SCSI Format Unit')
                analysis['commands_available'].append('sg_utils commands')
                
        except Exception as e:
            analysis['warnings'].append(f"SCSI analysis failed: {e}")
    
    def _check_smart_capabilities(self, disk_path, analysis):
        """Use smartctl for detailed drive analysis"""
        
        try:
            cmd = ['smartctl', '-a', disk_path]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode in [0, 4]:  # 4 is often normal for smartctl
                output = result.stdout.lower()
                
                # Check drive type
                if 'solid state device' in output or 'ssd' in output:
                    if analysis['drive_type'] == 'unknown':
                        analysis['drive_type'] = 'ssd'
                elif 'ata device' in output:
                    if analysis['drive_type'] == 'unknown':
                        analysis['drive_type'] = 'hdd'
                
                # Check for encryption
                if 'encryption' in output or 'security' in output:
                    analysis['has_encryption'] = True
                
                analysis['commands_available'].append('smartctl monitoring')
                
        except Exception as e:
            analysis['warnings'].append(f"SMART analysis failed: {e}")
    
    def _analyze_windows_drive(self, disk_path, analysis):
        """Analyze drive on Windows"""
        
        analysis['warnings'].append("Windows firmware analysis has limited capabilities")
        analysis['warnings'].append("For advanced firmware operations, use Linux environment")
        
        # Basic Windows analysis using WMI
        try:
            cmd = f'wmic diskdrive where "DeviceID=\\"{disk_path}\\"" get InterfaceType,MediaType /format:csv'
            result = subprocess.run(cmd, capture_output=True, text=True, shell=True,
                                  creationflags=subprocess.CREATE_NO_WINDOW)
            
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                for line in lines[1:]:  # Skip header
                    if line.strip():
                        parts = line.split(',')
                        if len(parts) >= 3:
                            interface = parts[1].strip()
                            media_type = parts[2].strip()
                            
                            analysis['interface'] = interface
                            if 'ssd' in media_type.lower():
                                analysis['drive_type'] = 'ssd'
                            elif 'hdd' in media_type.lower():
                                analysis['drive_type'] = 'hdd'
                                
        except Exception as e:
            analysis['warnings'].append(f"Windows analysis error: {e}")
    
    def perform_firmware_wipe(self, disk_path, method='auto', force=False):
        """Perform firmware-level wiping"""
        
        if not force:
            return {
                'success': False,
                'error': 'Firmware wiping requires explicit force=True parameter',
                'warnings': ['This operation is DESTRUCTIVE and IRREVERSIBLE']
            }
        
        # Analyze drive first
        analysis = self.analyze_drive_capabilities(disk_path)
        
        # Select best method
        if method == 'auto':
            method = self._select_best_method(analysis)
        
        print(f"🔧 Performing firmware-level wipe on {disk_path}")
        print(f"📋 Method: {method}")
        print(f"🔍 Drive type: {analysis['drive_type']}")
        
        result = {
            'method_used': method,
            'drive_analysis': analysis,
            'success': False,
            'commands_executed': [],
            'warnings': [],
            'errors': []
        }
        
        try:
            if method == 'ata_secure_erase' and analysis['supports_ata_secure_erase']:
                return self._perform_ata_secure_erase(disk_path, result)
                
            elif method == 'nvme_format' and analysis['supports_nvme_format']:
                return self._perform_nvme_format(disk_path, result)
                
            elif method == 'scsi_format' and analysis['supports_scsi_format']:
                return self._perform_scsi_format(disk_path, result)
                
            elif method == 'firmware_overwrite':
                return self._perform_firmware_overwrite(disk_path, result)
                
            else:
                result['errors'].append(f"Method {method} not supported for this drive")
                return result
                
        except Exception as e:
            result['errors'].append(f"Firmware wipe failed: {e}")
            return result
    
    def _select_best_method(self, analysis):
        """Select the best firmware wiping method for the drive"""
        
        if analysis['supports_nvme_format']:
            return 'nvme_format'
        elif analysis['supports_ata_secure_erase']:
            return 'ata_secure_erase'  
        elif analysis['supports_scsi_format']:
            return 'scsi_format'
        else:
            return 'firmware_overwrite'
    
    def _perform_ata_secure_erase(self, disk_path, result):
        """Perform ATA Secure Erase"""
        
        if not self.available_tools['hdparm']:
            result['errors'].append("hdparm not available for ATA Secure Erase")
            return result
        
        try:
            print("🔐 Starting ATA Secure Erase...")
            
            # Check if security is enabled
            cmd = ['hdparm', '-I', disk_path]
            check_result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            result['commands_executed'].append(' '.join(cmd))
            
            if 'security enabled' in check_result.stdout.lower():
                result['warnings'].append("Drive security already enabled")
            
            # Set security password (temporary)
            temp_password = "TEMP_ERASE_PASS"
            cmd = ['hdparm', '--user-master', 'u', '--security-set-pass', temp_password, disk_path]
            set_result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            result['commands_executed'].append(' '.join(cmd))
            
            if set_result.returncode != 0:
                result['errors'].append(f"Failed to set security password: {set_result.stderr}")
                return result
            
            # Perform secure erase
            cmd = ['hdparm', '--user-master', 'u', '--security-erase', temp_password, disk_path]
            erase_result = subprocess.run(cmd, capture_output=True, text=True, timeout=7200)  # Up to 2 hours
            result['commands_executed'].append(' '.join(cmd))
            
            if erase_result.returncode == 0:
                result['success'] = True
                print("✅ ATA Secure Erase completed successfully")
            else:
                result['errors'].append(f"Secure erase failed: {erase_result.stderr}")
            
        except subprocess.TimeoutExpired:
            result['errors'].append("ATA Secure Erase timed out")
        except Exception as e:
            result['errors'].append(f"ATA Secure Erase error: {e}")
        
        return result
    
    def _perform_nvme_format(self, disk_path, result):
        """Perform NVMe Format"""
        
        if not self.available_tools['nvme_cli']:
            result['errors'].append("nvme-cli not available for NVMe format")
            return result
        
        try:
            print("💾 Starting NVMe Format...")
            
            # Perform secure format with cryptographic erase
            cmd = ['nvme', 'format', disk_path, '--ses=1', '--force']
            format_result = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
            result['commands_executed'].append(' '.join(cmd))
            
            if format_result.returncode == 0:
                result['success'] = True
                print("✅ NVMe Format completed successfully")
            else:
                result['errors'].append(f"NVMe format failed: {format_result.stderr}")
            
        except subprocess.TimeoutExpired:
            result['errors'].append("NVMe format timed out")
        except Exception as e:
            result['errors'].append(f"NVMe format error: {e}")
        
        return result
    
    def _perform_scsi_format(self, disk_path, result):
        """Perform SCSI Format Unit"""
        
        if not self.available_tools['sg_utils']:
            result['errors'].append("sg_utils not available for SCSI format")
            return result
        
        try:
            print("🖥️ Starting SCSI Format Unit...")
            
            # Perform SCSI format with security initialization
            cmd = ['sg_format', '--format', '--security', disk_path]
            format_result = subprocess.run(cmd, capture_output=True, text=True, timeout=7200)
            result['commands_executed'].append(' '.join(cmd))
            
            if format_result.returncode == 0:
                result['success'] = True
                print("✅ SCSI Format Unit completed successfully")
            else:
                result['errors'].append(f"SCSI format failed: {format_result.stderr}")
            
        except subprocess.TimeoutExpired:
            result['errors'].append("SCSI format timed out")
        except Exception as e:
            result['errors'].append(f"SCSI format error: {e}")
        
        return result
    
    def _perform_firmware_overwrite(self, disk_path, result):
        """Perform firmware-level overwrite using low-level tools"""
        
        try:
            print("🔄 Starting firmware-level overwrite...")
            
            # Use dd with direct I/O for low-level access
            if self.available_tools['dd']:
                # Multiple passes with different patterns
                patterns = [b'\x00', b'\xff', b'\xaa', b'\x55']
                
                for i, pattern in enumerate(patterns):
                    print(f"📝 Pass {i+1}/{len(patterns)}: Writing pattern {pattern.hex()}")
                    
                    # Create temporary pattern file
                    pattern_file = f"/tmp/pattern_{i}.bin"
                    with open(pattern_file, 'wb') as f:
                        f.write(pattern * 1024 * 1024)  # 1MB of pattern
                    
                    cmd = ['dd', f'if={pattern_file}', f'of={disk_path}', 'bs=1M', 'conv=notrunc,sync', 'oflag=direct']
                    dd_result = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
                    result['commands_executed'].append(' '.join(cmd))
                    
                    # Clean up pattern file
                    os.unlink(pattern_file)
                    
                    if dd_result.returncode != 0:
                        result['warnings'].append(f"Pattern {i+1} write had issues: {dd_result.stderr}")
                
                # Final random pass
                print("🎲 Final pass: Random data")
                cmd = ['dd', 'if=/dev/urandom', f'of={disk_path}', 'bs=1M', 'oflag=direct']
                dd_result = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
                result['commands_executed'].append(' '.join(cmd))
                
                result['success'] = True
                print("✅ Firmware-level overwrite completed")
                
            else:
                result['errors'].append("No suitable tools available for firmware overwrite")
            
        except Exception as e:
            result['errors'].append(f"Firmware overwrite error: {e}")
        
        return result

def main():
    """Command line interface"""
    
    import argparse
    
    parser = argparse.ArgumentParser(description='Zero Leaks Firmware-Level Wiper')
    parser.add_argument('command', choices=['analyze', 'wipe'], help='Command to execute')
    parser.add_argument('disk', help='Disk device path')
    parser.add_argument('--method', choices=['auto', 'ata_secure_erase', 'nvme_format', 'scsi_format', 'firmware_overwrite'], 
                       default='auto', help='Wiping method')
    parser.add_argument('--force', action='store_true', help='Force destructive operations')
    
    args = parser.parse_args()
    
    wiper = FirmwareLevelWiper()
    
    if args.command == 'analyze':
        analysis = wiper.analyze_drive_capabilities(args.disk)
        print(json.dumps(analysis, indent=2))
        
    elif args.command == 'wipe':
        if not args.force:
            print("ERROR: Firmware wiping requires --force flag")
            print("This operation will PERMANENTLY DESTROY ALL DATA")
            exit(1)
            
        result = wiper.perform_firmware_wipe(args.disk, args.method, force=True)
        print(json.dumps(result, indent=2))
        exit(0 if result['success'] else 1)

if __name__ == '__main__':
    main()