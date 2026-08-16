"""
Script to add CinetPay API keys to .env file
"""
import os

env_path = os.path.join(os.path.dirname(__file__), '.env')

# CinetPay credentials
cinetpay_config = """
# --- CinetPay Payment Gateway ---
CINETPAY_API_KEY=143459870067b2ecff946dd7.59047762
CINETPAY_SITE_ID=105888043
CINETPAY_SECRET_KEY=112414020867b2ef474bb320.19729040
"""

try:
    # Check if .env exists
    if os.path.exists(env_path):
        # Read existing content
        with open(env_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check if CinetPay keys already exist
        if 'CINETPAY_API_KEY' in content:
            print("⚠️  CinetPay keys already exist in .env file")
            print("Please manually update them if needed")
        else:
            # Append CinetPay configuration
            with open(env_path, 'a', encoding='utf-8') as f:
                f.write(cinetpay_config)
            print("✅ CinetPay API keys added to .env file successfully")
    else:
        # Create new .env file with CinetPay keys
        with open(env_path, 'w', encoding='utf-8') as f:
            f.write(cinetpay_config)
        print("✅ .env file created with CinetPay API keys")
        
except PermissionError:
    print("❌ Permission denied: Cannot modify .env file")
    print("Please manually add these lines to your .env file:")
    print(cinetpay_config)
except Exception as e:
    print(f"❌ Error: {str(e)}")
    print("Please manually add these lines to your .env file:")
    print(cinetpay_config)
