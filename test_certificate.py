"""
Test certificate generation to verify PDF creation works correctly.
"""
import os
import sys
from datetime import datetime, timezone
from generate_certificate import generate_certificate

def test_certificate_generation():
    """Test the certificate generation with sample data"""
    
    # Create a sample wipe log
    with open("wipe.log", "w", encoding='utf-8') as f:
        f.write("=== Data Wiping Operation Log ===\n")
        f.write("Start Time (UTC): 2025-10-08T10:00:00Z\n")
        f.write("Asset: P:\\Training\\wipe-tool.htm\n")
        f.write("Method: dod\n")
        f.write("=== Operation Output ===\n")
        f.write("Wiping File: P:\\Training\\wipe-tool.htm\n")
        f.write("File size: 25937 bytes.\n")
        f.write("SUCCESS: File securely wiped.\n")
        f.write("=== End of Log ===\n")
    
    # Platform info
    platform_info = {
        'system': 'Windows',
        'machine': 'AMD64',
        'release': '10',
    }
    
    # Wipe details
    wipe_details = {
        'wipe_method': 'dod',
        'asset_serial': 'N/A',
        'start_time': '2025-10-08T10:00:00Z',
        'end_time': '2025-10-08T10:05:30Z',
        'wipe_result': 'Success',
        'technician': 'Test Technician',
        'witness': 'Test Witness',
        'asset_type': 'File',
        'metadata_removed': True,
        'verification_passed': True,
        'organization': 'Zero Leaks Data Wiping Service'
    }
    
    try:
        print("Testing certificate generation...")
        cert_json, cert_pdf = generate_certificate(
            "wipe.log",
            "P:\\Training\\wipe-tool.htm",
            platform_info,
            wipe_details
        )
        
        print(f"\n✅ Certificate generation successful!")
        print(f"   JSON file: {cert_json}")
        print(f"   PDF file: {cert_pdf}")
        
        # Check if files exist (they should be in the certificates folder)
        cert_dir = "certificates"
        json_path = os.path.join(cert_dir, cert_json)
        pdf_path = os.path.join(cert_dir, cert_pdf)
        
        json_exists = os.path.exists(json_path)
        pdf_exists = os.path.exists(pdf_path)
        
        print(f"\n   JSON exists: {json_exists}")
        print(f"   PDF exists: {pdf_exists}")
        
        if json_exists and pdf_exists:
            print("\n✅ All certificate files created successfully!")
            print(f"\nYou can now test the download functionality in the web app.")
            return True
        else:
            print("\n❌ Error: Certificate files were not created!")
            return False
            
    except Exception as e:
        print(f"\n❌ Certificate generation failed with error:")
        print(f"   {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_certificate_generation()
    sys.exit(0 if success else 1)
