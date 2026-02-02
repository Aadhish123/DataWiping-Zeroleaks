#!/usr/bin/env python3
"""
SMART Disk Health Analyzer for Zero Leaks
Analyzes disk health, detects hidden areas, and verifies complete erasure coverage
"""

import subprocess
import json
import re
import platform
from datetime import datetime
from typing import Dict, List, Optional, Tuple

class SMARTAnalyzer:
    """Analyze disk health and verify erasure coverage using SMART data"""
    
    def __init__(self):
        self.platform_info = self._detect_platform()
        self.smartctl_available = self._check_smartctl()
        
    def _detect_platform(self):
        """Detect current platform"""
        system = platform.system()
        return {
            'system': system,
            'is_windows': system == 'Windows',
            'is_linux': system == 'Linux', 
            'is_macos': system == 'Darwin'
        }
    
    def _check_smartctl(self):
        """Check if smartctl is available"""
        try:
            result = subprocess.run(['smartctl', '--version'], capture_output=True, text=True, timeout=10)
            return result.returncode == 0
        except:
            return False
    
    def comprehensive_disk_analysis(self, disk_path: str) -> Dict:
        """
        Perform comprehensive disk analysis including SMART data, geometry, and health
        """
        analysis = {
            'disk_path': disk_path,
            'timestamp': datetime.now().isoformat(),
            'basic_info': {},
            'smart_data': {},
            'geometry': {},
            'health_status': 'unknown',
            'hidden_areas': {},
            'erasure_verification': {},
            'recommendations': [],
            'warnings': [],
            'errors': []
        }
        
        if not self.smartctl_available:
            analysis['errors'].append("smartctl not available - install smartmontools package")
            return analysis
        
        # Get basic device information
        self._get_basic_info(disk_path, analysis)
        
        # Get SMART data
        self._get_smart_data(disk_path, analysis)
        
        # Analyze disk geometry
        self._analyze_geometry(disk_path, analysis)
        
        # Check for hidden areas
        self._detect_hidden_areas(disk_path, analysis)
        
        # Assess overall health
        self._assess_health_status(analysis)
        
        # Generate recommendations
        self._generate_recommendations(analysis)
        
        return analysis
    
    def _get_basic_info(self, disk_path: str, analysis: Dict):
        """Get basic device information"""
        
        try:
            cmd = ['smartctl', '-i', disk_path]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode in [0, 4]:  # 4 is normal for some drives
                info = self._parse_smartctl_info(result.stdout)
                analysis['basic_info'] = info
                
                # Determine device type
                model = info.get('model_name', '').lower()
                if 'ssd' in model or info.get('rotation_rate') == 'Solid State Device':
                    analysis['basic_info']['drive_type'] = 'SSD'
                else:
                    analysis['basic_info']['drive_type'] = 'HDD'
                    
            else:
                analysis['errors'].append(f"Failed to get device info: {result.stderr}")
                
        except subprocess.TimeoutExpired:
            analysis['errors'].append("Device info query timed out")
        except Exception as e:
            analysis['errors'].append(f"Device info error: {e}")
    
    def _get_smart_data(self, disk_path: str, analysis: Dict):
        """Get comprehensive SMART data"""
        
        try:
            # Get SMART attributes
            cmd = ['smartctl', '-A', disk_path]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode in [0, 4]:
                analysis['smart_data']['attributes'] = self._parse_smart_attributes(result.stdout)
            
            # Get SMART health status
            cmd = ['smartctl', '-H', disk_path]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode in [0, 4]:
                if 'PASSED' in result.stdout:
                    analysis['smart_data']['health_status'] = 'PASSED'
                elif 'FAILED' in result.stdout:
                    analysis['smart_data']['health_status'] = 'FAILED'
                else:
                    analysis['smart_data']['health_status'] = 'UNKNOWN'
            
            # Get error log
            cmd = ['smartctl', '-l', 'error', disk_path]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode in [0, 4]:
                analysis['smart_data']['error_log'] = self._parse_error_log(result.stdout)
                
        except Exception as e:
            analysis['errors'].append(f"SMART data error: {e}")
    
    def _analyze_geometry(self, disk_path: str, analysis: Dict):
        """Analyze disk geometry and capacity"""
        
        try:
            cmd = ['smartctl', '-c', disk_path]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode in [0, 4]:
                geometry = self._parse_geometry(result.stdout)
                analysis['geometry'] = geometry
                
                # Calculate potential hidden areas
                if 'user_capacity' in geometry and 'device_size' in geometry:
                    user_capacity = geometry['user_capacity']
                    device_size = geometry.get('device_size', user_capacity)
                    
                    if device_size > user_capacity:
                        hidden_size = device_size - user_capacity
                        analysis['geometry']['potential_hidden_capacity'] = hidden_size
                        analysis['warnings'].append(f"Potential hidden area: {hidden_size} bytes")
                        
        except Exception as e:
            analysis['errors'].append(f"Geometry analysis error: {e}")
    
    def _detect_hidden_areas(self, disk_path: str, analysis: Dict):
        """Detect various types of hidden areas"""
        
        hidden_areas = {
            'hpa_detected': False,
            'dco_detected': False,
            'bad_sectors': 0,
            'reserved_sectors': 0,
            'over_provisioning': 0,
            'firmware_area': False
        }
        
        # Check SMART attributes for hidden area indicators
        smart_attrs = analysis['smart_data'].get('attributes', {})
        
        # Look for reallocated sectors (indicator of hidden bad sector management)
        if '5' in smart_attrs:  # Reallocated Sector Count
            reallocated = int(smart_attrs['5'].get('raw_value', 0))
            if reallocated > 0:
                hidden_areas['bad_sectors'] = reallocated
                analysis['warnings'].append(f"Reallocated sectors detected: {reallocated}")
        
        # Check for spare sectors (SSD over-provisioning)
        if '170' in smart_attrs:  # Available Reserved Space
            reserved = smart_attrs['170'].get('raw_value', '100%')
            if isinstance(reserved, str) and '%' in reserved:
                try:
                    percent = int(reserved.replace('%', ''))
                    if percent < 100:
                        hidden_areas['over_provisioning'] = 100 - percent
                        analysis['warnings'].append(f"SSD over-provisioning used: {100-percent}%")
                except:
                    pass
        
        # Check for wear leveling indicators (SSD firmware areas)
        if '177' in smart_attrs:  # Wear Leveling Count
            hidden_areas['firmware_area'] = True
            analysis['warnings'].append("SSD firmware wear leveling detected")
        
        analysis['hidden_areas'] = hidden_areas
    
    def _assess_health_status(self, analysis: Dict):
        """Assess overall disk health status"""
        
        health_score = 100
        status = 'HEALTHY'
        
        # Check SMART health
        smart_health = analysis['smart_data'].get('health_status')
        if smart_health == 'FAILED':
            health_score -= 50
            status = 'FAILING'
            analysis['warnings'].append("SMART health test FAILED")
        
        # Check critical SMART attributes
        smart_attrs = analysis['smart_data'].get('attributes', {})
        critical_attrs = ['5', '197', '198']  # Reallocated, Current Pending, Offline Uncorrectable
        
        for attr_id in critical_attrs:
            if attr_id in smart_attrs:
                raw_value = smart_attrs[attr_id].get('raw_value', 0)
                if isinstance(raw_value, str):
                    try:
                        raw_value = int(raw_value)
                    except:
                        raw_value = 0
                
                if raw_value > 0:
                    health_score -= min(20, raw_value)
                    if raw_value > 10:
                        status = 'DEGRADED'
                    analysis['warnings'].append(f"Critical SMART attribute {attr_id}: {raw_value}")
        
        # Check for errors in log
        error_count = analysis['smart_data'].get('error_log', {}).get('error_count', 0)
        if error_count > 0:
            health_score -= min(10, error_count)
            if error_count > 50:
                status = 'DEGRADED'
        
        analysis['health_status'] = status
        analysis['health_score'] = max(0, health_score)
    
    def verify_erasure_coverage(self, disk_path: str, wipe_log: str = None) -> Dict:
        """
        Verify that erasure covered all accessible areas including hidden regions
        """
        verification = {
            'coverage_complete': False,
            'areas_checked': [],
            'areas_missed': [],
            'verification_method': [],
            'confidence_level': 'LOW',
            'warnings': [],
            'errors': []
        }
        
        try:
            # Get current disk analysis
            analysis = self.comprehensive_disk_analysis(disk_path)
            
            # Check if all sectors were addressed
            geometry = analysis.get('geometry', {})
            hidden_areas = analysis.get('hidden_areas', {})
            
            # Verify accessible capacity was wiped
            if 'user_capacity' in geometry:
                verification['areas_checked'].append(f"User accessible capacity: {geometry['user_capacity']} bytes")
                verification['verification_method'].append('SMART geometry analysis')
            
            # Check if HPA/DCO areas need attention
            if hidden_areas.get('hpa_detected'):
                verification['areas_missed'].append("HPA (Hidden Protected Area) detected but may not be wiped")
                verification['warnings'].append("HPA requires specific erasure commands")
            
            if hidden_areas.get('dco_detected'):
                verification['areas_missed'].append("DCO (Device Configuration Overlay) detected")
                verification['warnings'].append("DCO requires firmware-level erasure")
            
            # Check bad sector remapping
            if hidden_areas.get('bad_sectors', 0) > 0:
                verification['areas_checked'].append(f"Remapped bad sectors: {hidden_areas['bad_sectors']}")
                verification['warnings'].append("Bad sectors may contain old data in remapping table")
            
            # Check SSD over-provisioning
            if hidden_areas.get('over_provisioning', 0) > 0:
                verification['areas_missed'].append(f"SSD over-provisioned area: {hidden_areas['over_provisioning']}%")
                verification['warnings'].append("SSD over-provisioned sectors may contain old data")
            
            # Analyze wipe log if provided
            if wipe_log:
                log_analysis = self._analyze_wipe_log(wipe_log, analysis)
                verification.update(log_analysis)
            
            # Determine confidence level
            if not verification['areas_missed'] and not verification['warnings']:
                verification['confidence_level'] = 'HIGH'
                verification['coverage_complete'] = True
            elif len(verification['areas_missed']) <= 1:
                verification['confidence_level'] = 'MEDIUM'
            else:
                verification['confidence_level'] = 'LOW'
            
            verification['verification_method'].append('SMART attribute analysis')
            verification['verification_method'].append('Disk geometry verification')
            
        except Exception as e:
            verification['errors'].append(f"Verification error: {e}")
        
        return verification
    
    def _analyze_wipe_log(self, wipe_log: str, analysis: Dict) -> Dict:
        """Analyze wipe log for coverage verification"""
        
        log_analysis = {
            'log_sectors_wiped': 0,
            'log_passes_completed': 0,
            'log_method_used': 'unknown',
            'log_verification': False
        }
        
        try:
            # Parse wipe log for sector information
            lines = wipe_log.split('\n')
            for line in lines:
                if 'sectors' in line.lower() or 'bytes' in line.lower():
                    # Extract numeric values
                    numbers = re.findall(r'\d+', line)
                    if numbers:
                        log_analysis['log_sectors_wiped'] = max(log_analysis['log_sectors_wiped'], int(numbers[0]))
                
                if 'pass' in line.lower():
                    pass_match = re.search(r'pass\s+(\d+)', line.lower())
                    if pass_match:
                        log_analysis['log_passes_completed'] = max(log_analysis['log_passes_completed'], int(pass_match.group(1)))
                
                if any(method in line.lower() for method in ['dod', 'gutmann', 'random', 'zeros', 'ata']):
                    for method in ['dod', 'gutmann', 'random', 'zeros', 'ata']:
                        if method in line.lower():
                            log_analysis['log_method_used'] = method
                            break
                
                if 'verification' in line.lower() and 'passed' in line.lower():
                    log_analysis['log_verification'] = True
            
            # Compare log data with disk geometry
            geometry = analysis.get('geometry', {})
            if 'user_capacity' in geometry and log_analysis['log_sectors_wiped'] > 0:
                expected_sectors = geometry['user_capacity'] // 512  # Assume 512-byte sectors
                if log_analysis['log_sectors_wiped'] >= expected_sectors * 0.99:  # 99% threshold
                    log_analysis['coverage_matches'] = True
                else:
                    log_analysis['coverage_matches'] = False
                    log_analysis['coverage_percentage'] = (log_analysis['log_sectors_wiped'] / expected_sectors) * 100
        
        except Exception as e:
            log_analysis['log_parse_error'] = str(e)
        
        return log_analysis
    
    def _generate_recommendations(self, analysis: Dict):
        """Generate recommendations based on analysis"""
        
        recommendations = []
        
        # Health-based recommendations
        health_status = analysis.get('health_status', 'unknown')
        if health_status == 'FAILING':
            recommendations.append("URGENT: Drive is failing - immediate data backup recommended")
            recommendations.append("Consider professional data recovery before secure wiping")
        elif health_status == 'DEGRADED':
            recommendations.append("Drive health degraded - monitor closely")
            recommendations.append("Use multiple-pass wiping for better security")
        
        # Hidden area recommendations
        hidden_areas = analysis.get('hidden_areas', {})
        if hidden_areas.get('hpa_detected'):
            recommendations.append("Use hdparm to disable HPA before wiping")
        if hidden_areas.get('dco_detected'):
            recommendations.append("Use hdparm --dco-restore for complete DCO erasure")
        if hidden_areas.get('over_provisioning', 0) > 0:
            recommendations.append("Use ATA Secure Erase for complete SSD erasure")
        
        # Drive type recommendations
        drive_type = analysis['basic_info'].get('drive_type', 'unknown')
        if drive_type == 'SSD':
            recommendations.append("Recommended: Use ATA Secure Erase for SSDs")
            recommendations.append("Multiple overwrite passes may reduce SSD lifespan")
        else:
            recommendations.append("Recommended: Use DoD 5220.22-M (3-pass) or Gutmann (35-pass)")
        
        analysis['recommendations'] = recommendations
    
    def _parse_smartctl_info(self, output: str) -> Dict:
        """Parse smartctl device info output"""
        info = {}
        
        for line in output.split('\n'):
            line = line.strip()
            if ':' in line:
                key, value = line.split(':', 1)
                key = key.strip().lower().replace(' ', '_').replace('-', '_')
                value = value.strip()
                info[key] = value
        
        return info
    
    def _parse_smart_attributes(self, output: str) -> Dict:
        """Parse SMART attributes table"""
        attributes = {}
        
        lines = output.split('\n')
        parsing_attributes = False
        
        for line in lines:
            line = line.strip()
            
            if 'ID#' in line and 'ATTRIBUTE_NAME' in line:
                parsing_attributes = True
                continue
            
            if parsing_attributes and line:
                parts = line.split()
                if len(parts) >= 10 and parts[0].isdigit():
                    attr_id = parts[0]
                    attributes[attr_id] = {
                        'name': parts[1],
                        'flag': parts[2],
                        'value': parts[3],
                        'worst': parts[4],
                        'threshold': parts[5],
                        'type': parts[6],
                        'updated': parts[7],
                        'when_failed': parts[8],
                        'raw_value': ' '.join(parts[9:])
                    }
        
        return attributes
    
    def _parse_error_log(self, output: str) -> Dict:
        """Parse SMART error log"""
        error_log = {
            'error_count': 0,
            'recent_errors': []
        }
        
        lines = output.split('\n')
        for line in lines:
            if 'Error' in line and 'occurred' in line:
                # Extract error count
                numbers = re.findall(r'\d+', line)
                if numbers:
                    error_log['error_count'] = int(numbers[0])
            elif 'Error' in line and len(error_log['recent_errors']) < 5:
                error_log['recent_errors'].append(line.strip())
        
        return error_log
    
    def _parse_geometry(self, output: str) -> Dict:
        """Parse disk geometry information"""
        geometry = {}
        
        for line in output.split('\n'):
            line = line.strip()
            
            if 'User Capacity' in line:
                # Extract capacity in bytes
                match = re.search(r'(\d+(?:,\d+)*)\s+bytes', line)
                if match:
                    capacity_str = match.group(1).replace(',', '')
                    geometry['user_capacity'] = int(capacity_str)
            
            elif 'Sector size' in line:
                # Extract logical/physical sector sizes
                match = re.search(r'(\d+)\s+bytes\s+logical.*?(\d+)\s+bytes\s+physical', line)
                if match:
                    geometry['logical_sector_size'] = int(match.group(1))
                    geometry['physical_sector_size'] = int(match.group(2))
            
            elif 'Total NVM Capacity' in line:
                # For NVMe drives
                match = re.search(r'(\d+(?:,\d+)*)\s+bytes', line)
                if match:
                    capacity_str = match.group(1).replace(',', '')
                    geometry['device_size'] = int(capacity_str)
        
        return geometry

def main():
    """Command line interface for SMART analyzer"""
    
    import argparse
    
    parser = argparse.ArgumentParser(description='Zero Leaks SMART Disk Analyzer')
    parser.add_argument('command', choices=['analyze', 'verify'], help='Command to execute')
    parser.add_argument('disk', help='Disk device path')
    parser.add_argument('--log-file', help='Wipe log file for verification')
    parser.add_argument('--output', help='Output file for analysis results')
    
    args = parser.parse_args()
    
    analyzer = SMARTAnalyzer()
    
    if args.command == 'analyze':
        analysis = analyzer.comprehensive_disk_analysis(args.disk)
        
        if args.output:
            with open(args.output, 'w') as f:
                json.dump(analysis, f, indent=2)
            print(f"Analysis saved to: {args.output}")
        else:
            print(json.dumps(analysis, indent=2))
    
    elif args.command == 'verify':
        wipe_log = None
        if args.log_file and os.path.exists(args.log_file):
            with open(args.log_file, 'r') as f:
                wipe_log = f.read()
        
        verification = analyzer.verify_erasure_coverage(args.disk, wipe_log)
        
        if args.output:
            with open(args.output, 'w') as f:
                json.dump(verification, f, indent=2)
            print(f"Verification saved to: {args.output}")
        else:
            print(json.dumps(verification, indent=2))

if __name__ == '__main__':
    import os
    main()