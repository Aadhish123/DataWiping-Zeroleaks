# 🔍 Security Verification Guide - How to Check Everything

## Overview
This guide shows you **exactly how to verify WHO, WHEN, WHAT, WHERE, and WHY** for every data wipe operation in your system.

---

## 📊 Method 1: Python Security Log Viewer (Recommended)

### Quick Start
```bash
python view_security_logs.py
```

### Menu Options:
1. **View All Audit Logs** - See WHO wiped WHAT, WHEN, and WHY
2. **View Certificates** - See verification codes for each operation
3. **View User Activity** - See who's using the system
4. **View Suspicious Activity** - See security alerts
5. **View ToS Acceptance** - See who accepted terms
6. **Search by Username** - Find specific user's operations
7. **View All** - Complete security report

### What You'll See:

```
📋 Log ID: 1
   Status: ✅ SUCCESS
   👤 WHO: User ID #6 - Username: Sudish
   🕐 WHEN: 2026-01-15 20:57:59
   📁 WHAT: E:\SteamSetup (1).exe
   🔧 METHOD: purge_3pass
   📝 WHY: sample checking of wiping
   🌐 WHERE (IP): 27.5.246.53
   📍 WHERE (Location): Mumbai, Maharashtra, India
   💻 DEVICE: WIN-ABC123-DEF456
   🎫 CERTIFICATE: wipe_certificate_abc123.json
```

---

## 🌐 Method 2: Web-Based Verification (Public Access)

### For Anyone to Verify Operations:

**1. Go to Verification Portal:**
```
http://localhost:5000/verify
```

**2. Enter Verification Code:**
```
Format: VERIFY-XXXX-XXXX-XXXX
Example: VERIFY-1F23-4A5B-6C7D
```

**3. View Complete Details:**
- ✅ Who performed the wipe (username)
- ✅ When it was done (timestamp)
- ✅ What was wiped (file/folder path)
- ✅ How it was wiped (method used)
- ✅ Why it was done (stated purpose)
- ✅ Where they were (IP + geolocation)
- ✅ What device (hardware fingerprint)
- ✅ Certificate authenticity
- ✅ File size and duration

**Key Benefit:** No login required - perfect for auditors, compliance officers, law enforcement!

---

## 💻 Method 3: Direct Database Query (Advanced)

### Open Database:
```bash
sqlite3 users.db
```

### Query 1: View All Wipe Operations
```sql
SELECT 
    id,
    username,
    device_path,
    wipe_method,
    purpose,
    ip_address,
    geolocation,
    timestamp,
    hardware_info,
    success
FROM audit_logs
ORDER BY timestamp DESC
LIMIT 20;
```

### Query 2: Search Specific User
```sql
SELECT * FROM audit_logs 
WHERE username = 'Sudish'
ORDER BY timestamp DESC;
```

### Query 3: Find Suspicious Operations
```sql
SELECT 
    a.username,
    a.device_path,
    a.purpose,
    a.timestamp,
    s.activity_type,
    s.severity
FROM audit_logs a
LEFT JOIN suspicious_activity s ON a.user_id = s.user_id
WHERE s.severity = 'high';
```

### Query 4: Get User Statistics
```sql
SELECT 
    u.username,
    COUNT(a.id) as total_wipes,
    l.license_type,
    rl.operations_today,
    rl.last_reset
FROM users u
LEFT JOIN audit_logs a ON u.id = a.user_id
LEFT JOIN licenses l ON u.id = l.user_id
LEFT JOIN rate_limits rl ON u.id = rl.user_id
GROUP BY u.id;
```

### Query 5: View Certificates
```sql
SELECT 
    certificate_id,
    verification_code,
    device_path,
    wipe_method,
    created_at,
    file_size,
    duration
FROM certificates
ORDER BY created_at DESC;
```

---

## 🖥️ Method 4: View Through Web Dashboard

### For Logged-in Users:

**1. User Statistics Page:**
```
http://localhost:5000/user/statistics
```

Shows:
- Your total wipes today
- Rate limit status (3/3 for free users)
- License information
- Account details

**2. About Page:**
```
http://localhost:5000/about
```

Shows:
- System statistics
- Total operations performed
- Active users
- Security features

---

## 📱 Method 5: Real-Time Monitoring

### Watch Flask Terminal Output:

Every operation logs in real-time:

```
127.0.0.1 - - [15/Jan/2026 20:57:59] "POST /wipe HTTP/1.1" 200 -
✅ User 'Sudish' wiped E:\SteamSetup.exe
   Method: purge_3pass
   Purpose: sample checking of wiping
   IP: 27.5.246.53
   Location: Mumbai, India
```

### Enable Verbose Logging:
In [app.py](app.py), set:
```python
app.run(host="0.0.0.0", port=5000, debug=True)
```

---

## 🔍 What Gets Logged (15 Data Points)

### Personal Information:
1. **User ID** - Unique identifier
2. **Username** - Account name
3. **Phone Number** - 2FA linked number (in users table)

### Operation Details:
4. **Device Path** - Exact file/folder wiped
5. **Wipe Method** - Clear/Purge/Destroy/Gutmann/ATA
6. **Purpose** - User's stated reason (minimum 20 chars)
7. **Success Status** - True/False
8. **Duration** - Time taken in seconds
9. **File Size** - Bytes wiped

### Location & Device:
10. **IP Address** - Real internet IP
11. **Geolocation** - City, state, country
12. **Hardware Fingerprint** - Unique device ID
13. **Timestamp** - Exact date/time (UTC)

### Verification:
14. **Certificate ID** - Unique cert UUID
15. **Verification Code** - Public verification code

---

## 🎯 Common Use Cases

### For Administrators:
```bash
# View all operations today
python view_security_logs.py
# Select option 1 (View All Audit Logs)
```

### For Compliance Officers:
1. Get verification code from certificate
2. Visit http://localhost:5000/verify
3. Enter code
4. Download/print details

### For Law Enforcement:
```sql
-- Search by username
SELECT * FROM audit_logs WHERE username = 'suspect_name';

-- Search by IP
SELECT * FROM audit_logs WHERE ip_address = '27.5.246.53';

-- Search by date
SELECT * FROM audit_logs 
WHERE timestamp BETWEEN '2026-01-15' AND '2026-01-16';

-- Find high-volume users
SELECT username, COUNT(*) as wipe_count 
FROM audit_logs 
GROUP BY username 
HAVING wipe_count > 10
ORDER BY wipe_count DESC;
```

### For Auditors:
```bash
# Generate complete report
python view_security_logs.py
# Select option 7 (View All)
```

---

## 🚨 Security Features That Cannot Be Bypassed

### 1. **Permanent Logs**
- Cannot be deleted by users
- Stored in SQLite database
- Backed up automatically

### 2. **Hardware Binding**
- Unique device fingerprint captured
- Same computer = same fingerprint
- Cannot be spoofed easily

### 3. **IP Tracking**
- Real internet IP logged
- Geolocation saved
- VPN/Proxy still shows exit IP

### 4. **Rate Limiting**
- Free users: 3 wipes/day MAX
- Prevents mass destruction
- Reset daily at midnight

### 5. **Mandatory Purpose**
- Minimum 20 characters
- Must provide reason
- Logged permanently

### 6. **2FA Authentication**
- Phone number required
- SMS OTP verification
- Links real identity

### 7. **License Validation**
- Active license required
- Hardware-bound
- Cannot be shared

### 8. **ToS Acceptance**
- Legal liability acknowledged
- IP address logged
- Cannot proceed without accepting

### 9. **Third-Party Verification**
- Anyone can verify certificates
- No login required
- Tamper detection

### 10. **Suspicious Activity AI**
- Pattern detection
- Automatic flagging
- Admin alerts

---

## 📋 Sample Queries for Different Scenarios

### Scenario 1: "Find all operations by user X"
```sql
SELECT * FROM audit_logs 
WHERE username = 'X'
ORDER BY timestamp DESC;
```

### Scenario 2: "Show failed wipe attempts"
```sql
SELECT username, device_path, timestamp, purpose
FROM audit_logs 
WHERE success = 0;
```

### Scenario 3: "Find operations with suspicious purposes"
```sql
SELECT username, device_path, purpose, timestamp
FROM audit_logs 
WHERE purpose LIKE '%delete evidence%' 
   OR purpose LIKE '%hide%'
   OR purpose LIKE '%cover%';
```

### Scenario 4: "Show users who wiped multiple files today"
```sql
SELECT username, COUNT(*) as wipes_today
FROM audit_logs 
WHERE DATE(timestamp) = DATE('now')
GROUP BY username
HAVING wipes_today > 1;
```

### Scenario 5: "Find operations from specific location"
```sql
SELECT username, device_path, timestamp
FROM audit_logs 
WHERE geolocation LIKE '%Mumbai%';
```

---

## 🎓 For Your Hackathon Demo

### Show Judges This Workflow:

**Step 1: Perform Wipe**
```
1. Login → Wipe Tool
2. Fill purpose: "GDPR compliance - customer data deletion"
3. Select file
4. Start wipe
5. Download certificate
```

**Step 2: Verify It's Logged**
```bash
python view_security_logs.py
# Select option 1
# Show complete details
```

**Step 3: Public Verification**
```
1. Open browser (incognito/different computer)
2. Go to /verify
3. Enter verification code
4. Show: "Anyone can verify, no login needed!"
```

**Step 4: Show Cannot Be Deleted**
```sql
-- Try to delete (will fail due to triggers)
DELETE FROM audit_logs WHERE id = 1;
-- Show error or re-insertion
```

**Step 5: Show Law Enforcement Access**
```sql
-- Search by username
SELECT * FROM audit_logs WHERE username = 'criminal_name';
-- Show: Complete trail exists
```

---

## 💡 Key Talking Points

1. **"The data is gone, but the proof remains forever!"**
2. **"Anyone can verify operations independently"**
3. **"15 data points logged per operation"**
4. **"Cannot be deleted or tampered"**
5. **"Law enforcement has complete access"**
6. **"Rate limiting prevents mass destruction"**
7. **"Hardware fingerprint tracks devices"**
8. **"Mandatory purpose creates accountability"**

---

## 📞 Quick Reference

| What to Check | How to Check | Time |
|---------------|-------------|------|
| **All operations** | `python view_security_logs.py` → Option 1 | 10 sec |
| **Specific user** | `python view_security_logs.py` → Option 6 | 15 sec |
| **Verify certificate** | Open /verify → Enter code | 5 sec |
| **User stats** | `python view_security_logs.py` → Option 3 | 10 sec |
| **Suspicious activity** | `python view_security_logs.py` → Option 4 | 10 sec |
| **Direct SQL** | `sqlite3 users.db` → Run query | 30 sec |

---

## ✅ Verification Checklist

Before your hackathon demo, verify:

- [ ] Audit logs are being created
- [ ] Certificates have verification codes
- [ ] /verify portal works without login
- [ ] All 15 data points are captured
- [ ] Rate limiting is enforced
- [ ] Suspicious activity detection works
- [ ] ToS acceptance is required
- [ ] License validation works
- [ ] Hardware fingerprint is unique
- [ ] Geolocation is accurate

---

**Remember:** Every single wipe operation creates a **permanent, immutable record** that includes WHO did it, WHAT they wiped, WHEN they did it, WHERE they were, and WHY they did it. This makes criminal misuse impossible!

**For questions during demo:** "Let me show you the actual logs..." then run `python view_security_logs.py`

---

**Built with security and transparency in mind! 🔐**
