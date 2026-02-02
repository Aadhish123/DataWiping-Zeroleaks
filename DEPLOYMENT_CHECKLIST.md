# ✅ DEPLOYMENT CHECKLIST

Use this checklist before deploying the secured application to production.

---

## 🔧 PRE-DEPLOYMENT

### 1. Database Setup
- [ ] Run `python database.py` to create all tables
- [ ] Run `python setup_security.py` to create licenses
- [ ] Verify `users.db` file exists
- [ ] Check all 8 security tables created:
  - [ ] audit_logs
  - [ ] licenses
  - [ ] suspicious_activity
  - [ ] rate_limits
  - [ ] tos_acceptance
  - [ ] user_verification
  - [ ] kill_switch_log
- [ ] Backup `users.db` file

### 2. Code Review
- [ ] Review `security_utils.py` - all functions working
- [ ] Review `app.py` - security decorators applied
- [ ] Check imports in app.py
- [ ] Verify templates exist:
  - [ ] tos.html
  - [ ] admin_dashboard.html
  - [ ] wipe_tool.html (updated with security features)

### 3. Configuration
- [ ] Change Flask secret key: `app.secret_key = os.urandom(24)`
- [ ] Update admin check from `username == 'admin'` to proper RBAC
- [ ] Configure IP geolocation service limits
- [ ] Set production database path (consider PostgreSQL)
- [ ] Configure email alerts (if implemented)

### 4. Testing
- [ ] Test user registration + OTP
- [ ] Test ToS acceptance flow
- [ ] Test purpose declaration (reject <20 chars)
- [ ] Test wipe operation (verify audit log created)
- [ ] Test rate limiting (3 wipes, then blocked)
- [ ] Test license validation
- [ ] Test admin dashboard access
- [ ] Test suspicious activity detection
- [ ] Test remote kill switch

---

## 🚀 DEPLOYMENT

### 5. Server Setup
- [ ] Use HTTPS only (no HTTP)
- [ ] Configure firewall rules
- [ ] Set up SSL certificate
- [ ] Configure reverse proxy (nginx/apache)
- [ ] Set environment variables
- [ ] Install Python dependencies:
  ```bash
  pip install flask werkzeug requests fpdf qrcode
  ```

### 6. Security Hardening
- [ ] Disable debug mode: `app.debug = False`
- [ ] Use production WSGI server (gunicorn/waitress)
- [ ] Set secure session cookies
- [ ] Configure CORS properly
- [ ] Enable rate limiting at server level
- [ ] Set up fail2ban for brute force protection
- [ ] Configure backup schedule
- [ ] Set up log rotation

### 7. Monitoring
- [ ] Set up application monitoring (Sentry, etc.)
- [ ] Configure admin email alerts
- [ ] Set up database backup automation
- [ ] Monitor disk space for audit logs
- [ ] Set up uptime monitoring
- [ ] Configure error logging

---

## 📋 POST-DEPLOYMENT

### 8. Verification
- [ ] Test complete user flow (sign up → wipe)
- [ ] Verify audit logs are being created
- [ ] Check admin dashboard loads
- [ ] Test rate limiting is enforced
- [ ] Verify ToS acceptance is required
- [ ] Test purpose declaration is mandatory
- [ ] Check suspicious activity detection
- [ ] Verify certificates are generated

### 9. Documentation
- [ ] Provide SECURITY_FEATURES.md to team
- [ ] Train support staff on admin dashboard
- [ ] Document incident response procedures
- [ ] Create law enforcement cooperation protocol
- [ ] Document backup/restore procedures
- [ ] Create user guides with security warnings

### 10. Legal & Compliance
- [ ] Review Terms of Service with legal counsel
- [ ] Ensure compliance with local data protection laws
- [ ] Document data retention policies
- [ ] Establish law enforcement contact procedures
- [ ] Consider insurance for data protection
- [ ] Keep audit logs for required retention period

---

## 🛡️ ONGOING MAINTENANCE

### Daily:
- [ ] Monitor admin dashboard for suspicious activity
- [ ] Review unresolved flags
- [ ] Check system health

### Weekly:
- [ ] Backup database
- [ ] Review audit log patterns
- [ ] Check disk space
- [ ] Update security rules if needed

### Monthly:
- [ ] Review Terms of Service
- [ ] Analyze usage statistics
- [ ] Update documentation
- [ ] Security patch updates
- [ ] Export compliance reports

---

## 🚨 INCIDENT RESPONSE

### If Misuse Suspected:
1. [ ] Do NOT delete any data
2. [ ] Suspend the account immediately
3. [ ] Export all audit logs for the user
4. [ ] Preserve certificate files
5. [ ] Document the incident
6. [ ] Contact law enforcement if necessary
7. [ ] Follow legal counsel advice

### If Breach Suspected:
1. [ ] Isolate affected systems
2. [ ] Preserve evidence
3. [ ] Contact security team
4. [ ] Review audit logs for unauthorized access
5. [ ] Reset admin credentials
6. [ ] Notify affected users (if required by law)
7. [ ] Document the breach

---

## 📊 METRICS TO TRACK

### User Metrics:
- Total users registered
- Active users (daily/weekly/monthly)
- Wipes performed (total, by user, by day)
- Average wipes per user
- Quota utilization

### Security Metrics:
- Suspicious activity flags (total, by severity)
- Auto-suspended accounts
- Manually suspended accounts
- Rate limit hits
- License deactivations
- VPN/Proxy detections

### System Metrics:
- Database size growth
- Audit log entries per day
- Certificate files generated
- Server uptime
- Error rate

---

## 🎯 SUCCESS CRITERIA

Your deployment is successful if:
- ✅ Users can sign up and perform legitimate wipes
- ✅ All operations are logged in audit_logs table
- ✅ Rate limits are enforced (blocks after 3 wipes)
- ✅ ToS acceptance is required
- ✅ Purpose declaration is mandatory
- ✅ Admin dashboard shows all activity
- ✅ Suspicious patterns are detected and flagged
- ✅ Remote kill switch can deactivate accounts
- ✅ Audit trail can be exported for authorities

---

## 📞 SUPPORT CONTACTS

### Internal:
- Technical Issues: [Your IT Team]
- Security Incidents: [Security Team]
- Legal Questions: [Legal Counsel]

### External:
- Law Enforcement Liaison: [Contact Info]
- Security Consultants: [If applicable]

---

## 📝 FINAL NOTES

### Remember:
1. **Audit logs are sacred** - Never delete them
2. **Rate limits protect everyone** - Don't disable them
3. **Purpose declarations are evidence** - Keep them
4. **Admin access is powerful** - Restrict it carefully
5. **Cooperation is mandatory** - Honor legal requests
6. **Users are accountable** - ToS makes this clear
7. **Monitoring is continuous** - Check dashboard regularly

### Emergency Commands:

**Suspend User:**
```python
python
from security_utils import suspend_account
suspend_account(user_id=123, reason="Evidence destruction suspected")
exit()
```

**Kill License:**
```python
python
from security_utils import remote_kill_switch
remote_kill_switch(user_id=123, reason="Law enforcement request")
exit()
```

**Export Logs:**
```bash
sqlite3 users.db
.mode csv
.output user_logs.csv
SELECT * FROM audit_logs WHERE user_id = 123;
.quit
```

---

## ✅ DEPLOYMENT SIGN-OFF

Once all items are checked:

- [ ] Technical Lead: _____________________ Date: _______
- [ ] Security Review: ____________________ Date: _______
- [ ] Legal Review: _______________________ Date: _______
- [ ] Management Approval: ________________ Date: _______

---

**🎉 YOUR APPLICATION IS READY FOR SECURE DEPLOYMENT! 🎉**

---

*Deployment Checklist v1.0 - December 21, 2025*