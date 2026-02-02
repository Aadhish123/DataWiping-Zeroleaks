#!/usr/bin/env python3
"""
HPA/DCO Detection and Erasure Module
Handles Hidden Protected Areas and Device Configuration Overlay
"""

import subprocess
import platform
import os
import sys
import json
from datetime import datetime

class HPADCOHandler:
    """Handle HPA/DCO detection and secure erasure"""
    
    def __init__(self):
        self.platform_info = self._detect_platform()
        self.hdparm_available = self._check_hdparm()
        
    def _detect_platform(self):
        """Detect current platform"""
        system = platform.system()
        return {
            'system': system,
            'is_windows': system == 'Windows',
            'is_linux': system == 'Linux',
            'is_macos': system == 'Darwin'
        }
    
    def _check_hdparm(self):
        """Check if hdparm is available (Linux)"""
        if not self.platform_info['is_linux']:
            return False
        try:
            result = subprocess.run(['which', 'hdparm'], capture_output=True, text=True)
            return result.returncode == 0
        except:
            return False
    
    def detect_hpa_dco(self, disk_path):
        """
        Detect HPA (Hidden Protected Area) and DCO (Device Configuration Overlay)
        Returns dict with detection results
        """
        results = {
            'hpa_detected': False,
            'dco_detected': False,
            'hpa_size': 0,
            'dco_size': 0,
            'native_capacity': 0,
            'accessible_capacity': 0,
            'hidden_capacity': 0,
            'supports_hpa': False,
            'supports_dco': False,
            'detection_method': None,
            'warnings': [],
            'commands_used': []
        }
        
        if self.platform_info['is_linux']:
            return self._detect_hpa_dco_linux(disk_path, results)
        elif self.platform_info['is_windows']:
            return self._detect_hpa_dco_windows(disk_path, results)
        else:
            results['warnings'].append("HPA/DCO detection not supported on this platform")
            return results
    
    def _detect_hpa_dco_linux(self, disk_path, results):
        """Linux HPA/DCO detection using hdparm"""
        if not self.hdparm_available:
            results['warnings'].append("hdparm not available. Install with: sudo apt install hdparm")
            return results
        
        results['detection_method'] = 'hdparm (Linux)'
        
        try:
            # Check if drive supports HPA
            cmd = ['hdparm', '-N', disk_path]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            results['commands_used'].append(' '.join(cmd))
            
            if result.returncode == 0:
                output = result.stdout.lower()
                
                # Parse HPA information
                if 'max sectors' in output:
                    lines = result.stdout.split('\n')
                    for line in lines:
                        if 'max sectors' in line.lower():
                            # Extract sector information
                            parts = line.split()
                            if len(parts) >= 4:
                                try:
                                    accessible = int(parts[0])
                                    native = int(parts[3].replace(',', ''))
                                    results['accessible_capacity'] = accessible
                                    results['native_capacity'] = native
                                    results['hidden_capacity'] = native - accessible
                                    
                                    if native > accessible:
                                        results['hpa_detected'] = True
                                        results['hpa_size'] = native - accessible
                                        results['supports_hpa'] = True
                                except ValueError:
                                    pass
                
                if 'hpa is enabled' in output or results['hpa_detected']:
                    results['supports_hpa'] = True
            
            # Check for DCO (Device Configuration Overlay)
            cmd = ['hdparm', '--dco-identify', disk_path]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            results['commands_used'].append(' '.join(cmd))
            
            if result.returncode == 0 and 'dco' in result.stdout.lower():
                results['supports_dco'] = True
                # DCO detection is more complex and may require additional parsing
                if 'dco is set' in result.stdout.lower():
                    results['dco_detected'] = True
            
        except subprocess.TimeoutExpired:
            results['warnings'].append("HPA/DCO detection timed out")
        except Exception as e:
            results['warnings'].append(f"HPA/DCO detection error: {str(e)}")
        
        return results
    
    def _detect_hpa_dco_windows(self, disk_path, results):
        """Windows HPA/DCO detection using diskpart and WMI"""
        results['detection_method'] = 'WMI/diskpart (Windows)'
        
        try:
            # Use WMIC to get disk information
            cmd = f'wmic diskdrive where "DeviceID=\\"{disk_path}\\"" get Size,Index,MediaType /format:csv'
            result = subprocess.run(cmd, capture_output=True, text=True, shell=True, 
                                  creationflags=subprocess.CREATE_NO_WINDOW)
            results['commands_used'].append(cmd)
            
            if result.returncode == 0:
                # Parse output for size information
                lines = result.stdout.strip().split('\n')
                for line in lines[1:]:  # Skip header
                    if line.strip():
                        parts = line.split(',')
                        if len(parts) >= 4:
                            try:
                                size = int(parts[3])
                                results['accessible_capacity'] = size // 512  # Convert to sectors
                            except (ValueError, IndexError):
                                pass
            
            # Check for potential HPA using ATA commands (requires admin privileges)
            # This is a simplified check - real implementation would need ATA pass-through
            results['warnings'].append("Windows HPA/DCO detection requires specialized tools")
            results['warnings'].append("Consider using Linux environment for full HPA/DCO support")
            
        except Exception as e:
            results['warnings'].append(f"Windows HPA/DCO detection error: {str(e)}")
        
        return results
    
    def erase_hpa_dco(self, disk_path, force=False):
        """
        Securely erase HPA and DCO areas
        WARNING: This is destructive and may brick the drive if not done correctly
        """
        results = {
            'hpa_erased': False,
            'dco_erased': False,
            'warnings': [],
            'commands_executed': [],
            'errors': [],
            'success': False
        }
        
        if not force:
            results['errors'].append("HPA/DCO erasure requires explicit force=True parameter")
            return results
        
        # First detect what we're dealing with
        detection = self.detect_hpa_dco(disk_path)
        
        if not (detection['hpa_detected'] or detection['dco_detected']):
            results['warnings'].append("No HPA or DCO detected - nothing to erase")
            results['success'] = True
            return results
        
        if self.platform_info['is_linux']:
            return self._erase_hpa_dco_linux(disk_path, detection, results)
        elif self.platform_info['is_windows']:
            return self._erase_hpa_dco_windows(disk_path, detection, results)
        else:
            results['errors'].append("HPA/DCO erasure not supported on this platform")
            return results
    
    def _erase_hpa_dco_linux(self, disk_path, detection, results):
        """Linux HPA/DCO erasure using hdparm"""
        if not self.hdparm_available:
            results['errors'].append("hdparm not available for HPA/DCO erasure")
            return results
        
        try:
            # Erase HPA if detected
            if detection['hpa_detected']:
                print(f"WARNING: About to erase HPA on {disk_path}")
                print("This will make the full native capacity accessible")
                
                # Disable HPA (make full capacity accessible)
                native_capacity = detection['native_capacity']
                cmd = ['hdparm', '-N', f'p{native_capacity}', disk_path]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
                results['commands_executed'].append(' '.join(cmd))
                
                if result.returncode == 0:
                    results['hpa_erased'] = True
                    print(f"HPA disabled - full capacity now accessible")
                else:
                    results['errors'].append(f"Failed to disable HPA: {result.stderr}")
            
            # Erase DCO if detected (extremely dangerous!)
            if detection['dco_detected']:
                print(f"WARNING: About to erase DCO on {disk_path}")
                print("This is EXTREMELY DANGEROUS and may brick the drive!")
                
                # DCO restoration (use with extreme caution)
                cmd = ['hdparm', '--dco-restore', disk_path]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
                results['commands_executed'].append(' '.join(cmd))
                
                if result.returncode == 0:
                    results['dco_erased'] = True
                    print(f"DCO restored - drive may need power cycle")
                else:
                    results['errors'].append(f"Failed to restore DCO: {result.stderr}")
            
            results['success'] = results['hpa_erased'] or results['dco_erased'] or (
                not detection['hpa_detected'] and not detection['dco_detected']
            )
            
        except subprocess.TimeoutExpired:
            results['errors'].append("HPA/DCO erasure timed out")
        except Exception as e:
            results['errors'].append(f"HPA/DCO erasure error: {str(e)}")
        
        return results
    
    def _erase_hpa_dco_windows(self, disk_path, detection, results):
        """Windows HPA/DCO erasure (limited support)"""
        results['warnings'].append("Windows HPA/DCO erasure has limited support")
        results['warnings'].append("For complete HPA/DCO erasure, use Linux with hdparm")
        results['errors'].append("Full HPA/DCO erasure not implemented for Windows")
        return results
    
    def generate_hpa_dco_report(self, disk_path):
        """Generate comprehensive HPA/DCO analysis report"""
        detection = self.detect_hpa_dco(disk_path)
        
        report = {
            'disk_path': disk_path,
            'timestamp': datetime.now().isoformat(),
            'platform': self.platform_info['system'],
            'detection_results': detection,
            'recommendations': [],
            'risk_assessment': 'LOW'
        }
        
        # Add recommendations based on findings
        if detection['hpa_detected']:
            report['recommendations'].append("HPA detected - consider disabling for complete data erasure")
            report['risk_assessment'] = 'HIGH'
        
        if detection['dco_detected']:
            report['recommendations'].append("DCO detected - professional erasure recommended")
            report['risk_assessment'] = 'CRITICAL'
        
        if detection['hidden_capacity'] > 0:
            hidden_gb = (detection['hidden_capacity'] * 512) / (1024**3)
            report['recommendations'].append(f"Hidden capacity: {hidden_gb:.2f} GB - may contain data")
            
        if not detection['supports_hpa'] and not detection['supports_dco']:
            report['recommendations'].append("Drive does not support HPA/DCO - standard wiping sufficient")
            
        if self.platform_info['is_windows']:
            report['recommendations'].append("Use Linux environment for complete HPA/DCO handling")
        
        return report

def main():
    """Command line interface for HPA/DCO handler"""
    if len(sys.argv) < 3:
        print("Usage: python hpa_dco_handler.py <command> <disk_path> [options]")
        print("Commands:")
        print("  detect /dev/sda    - Detect HPA/DCO")
        print("  report /dev/sda    - Generate detailed report")
        print("  erase /dev/sda     - Erase HPA/DCO (dangerous!)")
        sys.exit(1)
    
    command = sys.argv[1]
    disk_path = sys.argv[2]
    
    handler = HPADCOHandler()
    
    if command == 'detect':
        results = handler.detect_hpa_dco(disk_path)
        print(json.dumps(results, indent=2))
        
    elif command == 'report':
        report = handler.generate_hpa_dco_report(disk_path)
        print(json.dumps(report, indent=2))
        
    elif command == 'erase':
        print("WARNING: This will permanently erase HPA/DCO areas!")
        print("This operation is IRREVERSIBLE and may damage the drive!")
        confirm = input("Type 'ERASE_HPA_DCO' to confirm: ")
        
        if confirm == 'ERASE_HPA_DCO':
            results = handler.erase_hpa_dco(disk_path, force=True)
            print(json.dumps(results, indent=2))
        else:
            print("Operation cancelled")
            
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)

if __name__ == '__main__':
    main()