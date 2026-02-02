# 🔒 SECURITY FEATURES IMPLEMENTATION

## Overview
This document describes the comprehensive security measures implemented to prevent misuse of the ZeroLeaks data wiping application.

---

## 🛡️ IMPLEMENTED SECURITY FEATURES

### 1. **Comprehensive Audit Logging** ✅
- **Every operation is permanently logged** with:
  - User identity (ID, username)
  - IP address and geolocation
  - Device hardware fingerprint
  - Timestamp (UTC)
  - Purpose declaration (mandatory)
  - Operation details (path, method, result)
  - Certificate ID linking

**Location**: `security_utils.py` - `log_audit_event()`
**Database**: `audit_logs` table

### 2. **Mandatory Purpose Declaration** ✅
- Users MUST provide detailed reason (minimum 20 characters) before EVERY wipe
- Purpose is logged and permanently stored
- Cannot proceed without valid purpose
- Displayed in confirmation dialogs

**Implementation**: 
- Backend: [app.py](app.py#L526-L534)
- Frontend: [wipe_tool.html](templates/wipe_tool.html#L68-L81)

### 3. **Rate Limiting** ✅
- **Free users**: 3 wipes per day
- **Cooldown period**: 15 minutes between operations
- **Automatic tracking** via `rate_limits` table
- **Verified users** can have higher limits

**Location**: `security_utils.py` - `check_rate_limit()`, `increment_rate_limit()`

### 4. **License Activation System** ✅
- **Hardware-bound licenses** (MAC address + CPU ID)
- **Expiry dates** for time-limited access
- **Remote kill switch** capability
- **Online validation** before operations
- License types: free, premium, enterprise

**Location**: `security_utils.py` - `validate_license()`, `remote_kill_switch()`

### 5. **Suspicious Activity Detection** ✅
Automatically flags and monitors:
- High-frequency usage (>5 wipes in 24 hours)
- Multiple IP addresses
- Multiple geographic locations
- VPN/Proxy usage
- Unusual operating hours (2 AM - 5 AM)

**Auto-suspend**: Accounts with 2+ high-severity flags

**Location**: `security_utils.py` - `check_suspicious_activity()`

### 6. **IP Geolocation Tracking** ✅
- Real-time IP geolocation via ip-api.com
- Logs: Country, Region, City, ISP, Coordinates
- VPN/Proxy detection
- All logged per operation

**Location**: `security_utils.py` - `get_geolocation()`, `is_vpn_or_proxy()`

### 7. **Hardware Fingerprinting** ✅
- Unique hardware ID generation
- Based on: MAC address, CPU, hostname
- Binds licenses to specific machines
- Prevents license sharing

**Location**: `security_utils.py` - `get_hardware_id()`

### 8. **Terms of Service Enforcement** ✅
- **Legal disclaimers** with criminal liability warnings
- **Mandatory acceptance** before using wipe tools
- **Logged acceptance** with IP and timestamp
- Cannot proceed without acceptance

**Template**: [templates/tos.html](templates/tos.html)
**Route**: `/tos`, `/accept-tos`

### 9. **User Statistics Dashboard** ✅
- Real-time display of:
  - Daily wipe limit
  - Wipes used today
  - Remaining quota
  - Account status
  - Total lifetime wipes

**Route**: `/user/statistics`

### 10. **Admin Monitoring Dashboard** ✅
- View all audit logs
- Monitor suspicious activity
- See unresolved flags
- Track user patterns
- Real-time updates (30s refresh)

**Template**: [templates/admin_dashboard.html](templates/admin_dashboard.html)
**Route**: `/admin/dashboard` (admin only)

---

## 📊 DATABASE SCHEMA

### Enhanced Tables Created:

#### `audit_logs`
```sql
- user_id, username
- operation_type (wipe_success, wipe_failed, etc.)
- device_path, wipe_method
- purpose (mandatory user declaration)
- ip_address, user_agent
- geolocation, country_code
- timestamp, certificate_id
- hardware_info, success
```

#### `licenses`
```sql
- license_key (unique)
- license_type (free, premium, enterprise)
- hardware_id (MAC/CPU binding)
- activation_date, expiry_date
- is_active, max_wipes_per_day
```

#### `suspicious_activity`
```sql
- user_id, activity_type
- severity (low, medium, high)
- description, detected_at
- ip_address, resolved
```

#### `rate_limits`
```sql
- user_id, date
- wipe_count, last_wipe_time
```

#### `tos_acceptance`
```sql
- user_id, tos_version
- accepted_at, ip_address
```

#### `user_verification`
```sql
- user_id, verification_type
- document_path, verification_status
- submitted_at, verified_at
```

---

## 🚀 SETUP INSTRUCTIONS

### 1. Initialize Enhanced Database
```bash
python database.py
```

### 2. Setup Security for Existing Users
```bash
python setup_security.py
```

### 3. Install Required Dependencies
```bash
pip install requests
```

### 4. Run Application
```bash
python app.py
```

---

## 🎯 USAGE FLOW

### For End Users:

1. **Sign Up / Login** → OTP verification
2. **Accept Terms of Service** → Legal disclaimers, warnings
3. **Access Wipe Tool** → View statistics (remaining quota)
4. **Provide Purpose** → Mandatory 20+ character explanation
5. **Select Target** → File, folder, or disk
6. **Confirm Operation** → Legal warning in confirmation
7. **Audit Log Created** → All details permanently recorded
8. **Rate Limit Applied** → Counter incremented
9. **Certificate Generated** → Immutable proof

### For Administrators:

1. Login as admin user (username: "admin")
2. Access `/admin/dashboard`
3. Monitor:
   - All audit logs
   - Suspicious activity flags
   - User patterns
4. Take action:
   - Suspend accounts
   - Deactivate licenses
   - Export logs for law enforcement

---

## ⚖️ LEGAL COMPLIANCE

### Warning Messages Displayed:
- ⚠️ All operations are monitored and logged
- ⚠️ Misuse is a crime punishable by law
- ⚠️ Logs will be disclosed to authorities
- ⚠️ Evidence destruction is a federal offense

### Logged Information:
✓ User identity  
✓ Purpose declaration  
✓ IP address & location  
✓ Hardware fingerprint  
✓ Timestamp  
✓ Certificate linking  

### Enforcement:
- Automatic suspension for suspicious patterns
- Rate limits prevent abuse
- Remote kill switch for reported misuse
- Full audit trail for investigations

---

## 🔐 SECURITY DECORATORS

Use these decorators on routes:

```python
@require_license         # Validates active license
@require_rate_limit      # Enforces daily limits
@require_tos_acceptance  # Ensures ToS accepted
@login_required          # Standard authentication
```

**Example**:
```python
@app.route('/wipe', methods=['POST'])
@login_required
@require_tos_acceptance
@require_license
@require_rate_limit
def wipe_file_route():
    # ... wipe logic
    log_audit_event(...)  # Log everything
```

---

## 📈 MONITORING & ALERTS

### Automatic Flags:
| Trigger | Severity | Action |
|---------|----------|--------|
| >5 wipes in 24h | High | Flag + Alert |
| Multiple countries | High | Flag + Alert |
| VPN detected | Medium | Flag |
| Unusual hours | Low | Log only |
| 2+ High flags | Critical | **Auto-suspend** |

### Admin Alerts:
- Email notifications (implement SMTP)
- Dashboard real-time updates
- Export suspicious activity reports

---

## 🛠️ CONFIGURATION

### Rate Limits (in database):
```python
# Free users
daily_wipe_limit = 3
cooldown_minutes = 15

# Premium users (set via admin)
daily_wipe_limit = 20
cooldown_minutes = 5
```

### License Expiry:
```python
# Default free license
expiry = 1 year from signup
```

### ToS Version:
```python
tos_version = 'v1.0'
```

---

## 🚨 EMERGENCY PROCEDURES

### Reported Misuse:

1. **Immediate Action**:
```python
from security_utils import remote_kill_switch, suspend_account

# Deactivate user
remote_kill_switch(user_id=123, reason="Law enforcement request #12345")
suspend_account(user_id=123, reason="Evidence destruction suspected")
```

2. **Export Audit Trail**:
```sql
SELECT * FROM audit_logs WHERE user_id = 123 ORDER BY timestamp;
```

3. **Provide to Authorities**:
- Complete audit logs
- Certificate files
- Hardware fingerprints
- IP/geolocation history

---

## 📋 COMPLIANCE CHECKLIST

✅ Audit logging implemented  
✅ Purpose declaration mandatory  
✅ Rate limiting active  
✅ License system operational  
✅ ToS acceptance required  
✅ Suspicious activity detection  
✅ IP geolocation tracking  
✅ Hardware fingerprinting  
✅ Admin monitoring dashboard  
✅ Legal warnings displayed  
✅ Remote kill switch ready  
✅ Export capability for investigations  

---

## 🔄 NEXT STEPS (Future Enhancements)

### Phase 2 (Recommended):
- [ ] Blockchain certificate storage (immutable audit)
- [ ] Email notifications for suspicious activity
- [ ] Multi-factor authentication (beyond OTP)
- [ ] Government ID verification upload
- [ ] Integration with law enforcement portal
- [ ] AI-based pattern detection
- [ ] Mandatory waiting period (24h for high-risk operations)
- [ ] Geographic restrictions (country blocklist)
- [ ] Background check integration

### Phase 3 (Advanced):
- [ ] Watermarking (embed user ID in wiped sectors)
- [ ] Real-time monitoring service
- [ ] API for law enforcement queries
- [ ] Data retention policy enforcement
- [ ] Compliance reporting (GDPR, CCPA)

---

## 📞 SUPPORT

For security-related questions or to report suspicious activity:
- **Admin Dashboard**: `/admin/dashboard`
- **Audit Logs API**: `/admin/audit-logs`
- **User Stats API**: `/user/statistics`

---

## ⚠️ CRITICAL NOTES

1. **Default admin account**: Change the admin check in app.py from `username == 'admin'` to a proper role-based system
2. **Backup audit logs**: Regularly backup the `users.db` database
3. **Monitor disk space**: Audit logs grow over time
4. **Legal compliance**: Consult with legal counsel for your jurisdiction
5. **Data retention**: Comply with local data retention laws

---

## 📄 LICENSE & DISCLAIMER

This security implementation is designed to prevent misuse and ensure accountability. However:
- Users are solely responsible for their actions
- Developers are not liable for criminal misuse
- All operations are logged and traceable
- Cooperation with law enforcement is mandatory

**Use responsibly and legally.**

---

*Last Updated: December 21, 2025*
*Version: 1.0*