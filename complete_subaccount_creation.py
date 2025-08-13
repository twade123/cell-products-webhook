#!/usr/bin/env python3
"""
Webhook-driven sub-account creation system for Cell Products account.
Listens for survey completion webhooks and automatically creates sub-accounts.
"""

import requests
import json
import logging
from datetime import datetime
from flask import Flask, request, jsonify
import traceback
import os
import sys

# Configuration using environment variables only (Railway deployment)
print("✅ Loading Cell Products configuration from environment variables")
if not os.environ.get('GHL_API_KEY'):
    print("❌ GHL_API_KEY environment variable required")
    sys.exit(1)

GHL_CONFIG = {
    'api_key': os.environ.get('GHL_API_KEY'),
    'location_id': os.environ.get('GHL_LOCATION_ID', '10SapwdFnQK3Kwqp5ecv'),
    'company_name': 'cell_products',
    'base_url': os.environ.get('GHL_BASE_URL', 'https://rest.gohighlevel.com/v1')
}
print(f"🏢 Company: {GHL_CONFIG.get('company_name', 'cell_products')}")
print(f"📍 Location ID: {GHL_CONFIG.get('location_id', 'N/A')}")

# Configuration using loaded GHL config
CONFIG = {
    # Use API key from config system
    'company_api_key': GHL_CONFIG['api_key'],
    
    # Cell Products Location ID from config system
    'cell_products_location_id': GHL_CONFIG['location_id'],
    
    # API Configuration - Updated to services endpoint for better compliance
    'base_url': GHL_CONFIG.get('base_url', 'https://rest.gohighlevel.com/v1'),
    'webhook_auth_token': 'cell-products-survey-webhook-2025',
    
    # Default timezone for new sub-accounts
    'default_timezone': 'America/Phoenix'  # Cell Products is in Nevada/Arizona timezone
}

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

app = Flask(__name__)

def validate_webhook_auth(request):
    """Validate webhook authentication for Cell Products only."""
    auth_header = request.headers.get('Authorization')
    if not auth_header:
        logging.warning("❌ No Authorization header in webhook request")
        return False
    
    expected_token = f"Bearer {CONFIG['webhook_auth_token']}"
    is_valid = auth_header == expected_token
    
    if not is_valid:
        logging.warning(f"❌ Invalid webhook token. Expected: {expected_token}, Got: {auth_header}")
    
    return is_valid

def validate_cell_products_source(source_location_id):
    """Ensure webhook is coming from Cell Products account only."""
    if source_location_id != CONFIG['cell_products_location_id']:
        logging.error(f"❌ Unauthorized source location: {source_location_id}")
        logging.error(f"   Expected Cell Products ID: {CONFIG['cell_products_location_id']}")
        return False
    
    logging.info("✅ Webhook confirmed from Cell Products account")
    return True

def create_subaccount_from_survey_data(survey_data):
    """Create a new sub-account using survey submission data."""
    
    try:
        # Extract business name with enhanced debugging for space format compatibility
        logging.info(f"🔍 Raw survey data keys: {list(survey_data.keys())}")
        
        # Try each field individually to debug extraction
        business_name_candidates = {
            'business name': survey_data.get('business name'),
            'business_name': survey_data.get('business_name'),
            'businessName': survey_data.get('businessName'),
            'company': survey_data.get('company'),
            'companyName': survey_data.get('companyName'),
            'Provider Name': survey_data.get('Provider Name'),
            'Legal Company Name': survey_data.get('Legal Company Name')
        }
        
        logging.info(f"🔍 Business name candidates: {business_name_candidates}")
        
        business_name = ''
        for field_name, field_value in business_name_candidates.items():
            if field_value and str(field_value).strip():
                business_name = str(field_value).strip()
                logging.info(f"🔍 Found business name from field '{field_name}': '{business_name}'")
                break
                
        if not business_name:
            logging.error(f"🔍 No business name found in any candidate field")
        
        # Extract name fields with priority for separate fields (like successful test)
        # First try individual name fields (this is what worked)
        first_name = ''
        last_name = ''
        
        # Try individual name fields first (prioritize underscore format that worked)
        first_name_candidates = {
            'first_name': survey_data.get('first_name'),
            'firstName': survey_data.get('firstName'),
            'fname': survey_data.get('fname'),
            'Patient First Name': survey_data.get('Patient First Name')
        }
        
        last_name_candidates = {
            'last_name': survey_data.get('last_name'),
            'lastName': survey_data.get('lastName'),
            'lname': survey_data.get('lname'),
            'Patient Last Name': survey_data.get('Patient Last Name')
        }
        
        # Extract first name
        for field_name, field_value in first_name_candidates.items():
            if field_value and str(field_value).strip():
                first_name = str(field_value).strip()
                logging.info(f"🔍 Found first name from field '{field_name}': '{first_name}'")
                break
                
        # Extract last name
        for field_name, field_value in last_name_candidates.items():
            if field_value and str(field_value).strip():
                last_name = str(field_value).strip()
                logging.info(f"🔍 Found last name from field '{field_name}': '{last_name}'")
                break
        
        # Only if no separate name fields found, try parsing combined 'name' field
        if not first_name and not last_name:
            full_name = survey_data.get('name', '').strip()
            if full_name:
                # Enhanced name parsing to handle titles and multiple names
                name_parts = full_name.replace('Dr. ', '').replace('Mr. ', '').replace('Ms. ', '').replace('Mrs. ', '').strip().split(' ', 1)
                first_name = name_parts[0] if len(name_parts) > 0 else ''
                last_name = name_parts[1] if len(name_parts) > 1 else ''
                logging.info(f"🔍 Parsed combined name field '{full_name}' into: '{first_name}' '{last_name}'")
        
        email = (survey_data.get('email') or 
                survey_data.get('emailAddress') or 
                survey_data.get('Email') or 
                survey_data.get('Patient Email') or '').strip()
        
        phone = (survey_data.get('phone') or 
                survey_data.get('phoneNumber') or 
                survey_data.get('mobile') or 
                survey_data.get('Phone') or 
                survey_data.get('Patient Phone') or '').strip()
        
        # Enhanced validation with detailed error reporting
        validation_errors = []
        
        if not business_name:
            validation_errors.append(f"Missing business name. Checked fields: {list(business_name_candidates.keys())}")
            
        if not email:
            validation_errors.append(f"Missing email. Available fields: {list(survey_data.keys())}")
        
        if validation_errors:
            error_details = "; ".join(validation_errors)
            logging.error(f"🔍 Validation failed: {error_details}")
            logging.error(f"🔍 Full survey data: {json.dumps(survey_data, indent=2)}")
            raise ValueError(f"Required field validation failed: {error_details}")
        
        # Use fallback values for missing names (following successful test pattern)
        if not first_name:
            first_name = "Contact"
            logging.info(f"🔍 Using fallback first name: '{first_name}'")
        if not last_name:
            last_name = "Person"
            logging.info(f"🔍 Using fallback last name: '{last_name}'")
            
        logging.info(f"🔍 Final extracted fields - Business: '{business_name}', Name: '{first_name} {last_name}', Email: '{email}'")
        
        # Clean phone number
        clean_phone = phone.replace('+1', '').replace('-', '').replace('(', '').replace(')', '').replace(' ', '')
        
        # Build sub-account data
        subaccount_data = {
            "name": business_name,
            "companyId": GHL_CONFIG.get('company_id', 'UAXssdawIWAWD'),  # Required field from API spec
            "address": survey_data.get('address', ''),
            "city": survey_data.get('city', ''),
            "state": survey_data.get('state', ''),
            "postalCode": survey_data.get('zip_code', ''),
            "country": "US",
            "phone": f"+1{clean_phone}" if clean_phone else "",
            "website": survey_data.get('website', ''),
            "timezone": CONFIG['default_timezone'],
            "prospectInfo": {
                "firstName": first_name,
                "lastName": last_name,
                "email": email
            },
            "settings": {
                "allowDuplicateContact": False,
                "allowDuplicateOpportunity": False,
                "allowFacebookNameMerge": False,
                "disableContactTimezone": False
            }
        }
        
        # Log sub-account creation attempt
        logging.info(f"🚀 Creating sub-account for {business_name}")
        logging.info(f"👤 Contact: {first_name} {last_name} ({email})")
        logging.info(f"📊 Sub-account data: {json.dumps(subaccount_data, indent=2)}")
        
        # API headers for Cell Products company account
        headers = {
            "Authorization": f"Bearer {CONFIG['company_api_key']}",
            "Content-Type": "application/json",
            "Version": "2021-07-28"
        }
        
        url = f"{CONFIG['base_url']}/locations/"
        
        # Create the sub-account
        response = requests.post(url, headers=headers, json=subaccount_data)
        
        logging.info(f"📡 POST {url}")
        logging.info(f"📊 Status: {response.status_code}")
        
        if response.status_code in [200, 201]:
            result = response.json()
            subaccount_id = result.get('id', 'N/A')
            
            logging.info(f"🎉 Sub-account created successfully!")
            logging.info(f"🆔 Sub-account ID: {subaccount_id}")
            logging.info(f"🏢 Business: {business_name}")
            logging.info(f"👤 Contact: {first_name} {last_name} ({email})")
            
            return {
                'success': True,
                'sub_account_id': subaccount_id,
                'business_name': business_name,
                'contact_name': f"{first_name} {last_name}",
                'email': email,
                'created_at': datetime.now().isoformat()
            }
        else:
            error_msg = f"Sub-account creation failed: {response.status_code} - {response.text}"
            logging.error(f"❌ {error_msg}")
            return {
                'success': False,
                'error': error_msg
            }
            
    except Exception as e:
        error_msg = f"Error creating sub-account: {str(e)}"
        logging.error(f"❌ {error_msg}")
        logging.error(traceback.format_exc())
        return {
            'success': False,
            'error': error_msg
        }

@app.route('/webhook/survey-completion', methods=['POST'])
def handle_survey_completion():
    """Handle survey completion webhook from Cell Products account."""
    
    try:
        # Log incoming webhook
        logging.info("📝 Survey completion webhook received")
        logging.info(f"🔗 Headers: {dict(request.headers)}")
        
        # GHL doesn't send Authorization headers by default - skip auth for now
        # TODO: Implement IP whitelist or webhook signature validation for security
        # if not validate_webhook_auth(request):
        #     return jsonify({"error": "Unauthorized"}), 401
        
        # Get webhook payload
        payload = request.get_json()
        if not payload:
            logging.error("❌ No JSON payload received")
            return jsonify({"error": "No JSON payload"}), 400
        
        logging.info(f"📦 Webhook payload: {json.dumps(payload, indent=2)}")
        
        # GHL webhook payload structure analysis
        logging.info(f"📦 Full webhook payload structure: {json.dumps(payload, indent=2)}")
        
        # Handle different GHL webhook formats
        # GHL sends form submissions, survey responses, etc. in various formats
        event_type = payload.get('type') or payload.get('event') or 'unknown'
        logging.info(f"📋 Webhook event type: {event_type}")
        
        # Extract location ID from various possible fields
        source_location_id = (payload.get('locationId') or 
                            payload.get('location_id') or 
                            payload.get('location', {}).get('id', ''))
        
        if source_location_id and not validate_cell_products_source(source_location_id):
            return jsonify({"error": "Unauthorized source location"}), 403
        
        # Extract survey/form data from various possible structures
        # GHL sends form fields directly at the top level of the payload
        survey_data = payload.copy()
        
        # CRITICAL FIX: Convert "business name" (space) to "business_name" (underscore) since underscore format works
        if 'business name' in survey_data and 'business_name' not in survey_data:
            survey_data['business_name'] = survey_data['business name']
            logging.info(f'🔧 Normalized "business name" to "business_name": {survey_data["business_name"]}')
        
        # Convert combined "name" field to separate first_name/last_name fields (like successful test)
        if 'name' in survey_data and 'first_name' not in survey_data and 'last_name' not in survey_data:
            full_name = str(survey_data['name']).replace('Dr. ', '').replace('Mr. ', '').replace('Ms. ', '').replace('Mrs. ', '').strip()
            name_parts = full_name.split(' ', 1)
            survey_data['first_name'] = name_parts[0] if len(name_parts) > 0 else ''
            survey_data['last_name'] = name_parts[1] if len(name_parts) > 1 else ''
            logging.info(f'🔧 Normalized "name" field "{full_name}" to separate fields: {survey_data["first_name"]} {survey_data["last_name"]}')
        
        logging.info(f"📊 Normalized survey data keys: {list(survey_data.keys())}")
        
        survey_id = (payload.get('formId') or 
                    payload.get('survey_id') or 
                    payload.get('id', ''))
        
        # Validate survey data
        if not survey_data:
            logging.error("❌ No survey data in webhook")
            return jsonify({"error": "No survey data"}), 400
        
        # Debug: Log all available field names for troubleshooting
        logging.info(f"📊 Available survey fields: {list(survey_data.keys())}")
        logging.info(f"📊 Survey data sample (first 10 fields): {dict(list(survey_data.items())[:10])}")
        
        # Enhanced webhook processing to match successful test pattern
        # Log processing start with improved field detection
        contact_name_parts = []
        
        # Try different name field combinations (prioritize separate fields like successful test)
        first_name_check = survey_data.get('first_name') or survey_data.get('firstName')
        last_name_check = survey_data.get('last_name') or survey_data.get('lastName')
        
        if first_name_check and last_name_check:
            contact_name_parts = [first_name_check, last_name_check]
        elif survey_data.get('name'):
            # Parse combined name field
            name_parts = str(survey_data.get('name')).replace('Dr. ', '').strip().split(' ', 1)
            contact_name_parts = name_parts
        
        contact_name = ' '.join(contact_name_parts) if contact_name_parts else 'Unknown'
        
        # Log key fields for debugging
        business_name_debug = (survey_data.get('business_name') or 
                             survey_data.get('company') or 'NOT_FOUND')
        
        logging.info(f"🚀 Processing survey completion for: {contact_name}")
        logging.info(f"🏢 Business field detected: '{business_name_debug}'")
        logging.info(f"📝 Survey ID: {survey_id}")
        logging.info(f"📍 Source: Cell Products ({source_location_id})")
        logging.info(f"🔍 Field format type: {'separate_names' if first_name_check else 'combined_name'}")
        
        # Create sub-account
        result = create_subaccount_from_survey_data(survey_data)
        
        if result['success']:
            response_data = {
                "success": True,
                "message": "Sub-account created successfully from survey",
                "sub_account_id": result['sub_account_id'],
                "business_name": result['business_name'],
                "contact_name": result['contact_name'],
                "email": result['email'],
                "created_at": result['created_at'],
                "timestamp": datetime.now().isoformat()
            }
            
            logging.info(f"✅ Survey webhook processed successfully")
            logging.info(f"🎉 Sub-account {result['sub_account_id']} created for {result['business_name']}")
            
            return jsonify(response_data), 200
        else:
            error_response = {
                "success": False,
                "error": result['error'],
                "timestamp": datetime.now().isoformat()
            }
            
            logging.error(f"❌ Sub-account creation failed: {result['error']}")
            return jsonify(error_response), 500
            
    except Exception as e:
        error_msg = f"Survey webhook processing error: {str(e)}"
        logging.error(f"❌ {error_msg}")
        logging.error(traceback.format_exc())
        
        return jsonify({
            "success": False,
            "error": error_msg,
            "timestamp": datetime.now().isoformat()
        }), 500

@app.route('/webhook/test', methods=['GET', 'POST'])
def test_webhook():
    """Test endpoint for webhook functionality."""
    
    if request.method == 'GET':
        return jsonify({
            "status": "cell_products_survey_webhook_active",
            "timestamp": datetime.now().isoformat(),
            "endpoints": {
                "survey_completion": "/webhook/survey-completion",
                "test": "/webhook/test",
                "health": "/health"
            },
            "account": "Cell Products Only",
            "location_id": CONFIG['cell_products_location_id']
        })
    
    # POST test with sample survey data
    sample_payload = {
        "event": "survey_completion",
        "timestamp": datetime.now().isoformat(),
        "survey_id": "test_survey_123",
        "location_id": CONFIG['cell_products_location_id'],
        "survey_data": {
            "first_name": "Test",
            "last_name": "Business",
            "email": "test@testbusiness.com",
            "phone": "+1234567890",
            "business_name": "Test Business LLC",
            "website": "https://testbusiness.com",
            "address": "123 Business Street",
            "city": "Phoenix",
            "state": "AZ",
            "zip_code": "85001",
            "service_interest": "premium_package"
        }
    }
    
    logging.info("🧪 Test webhook triggered with sample survey data")
    return jsonify({
        "message": "Test webhook received",
        "sample_payload": sample_payload,
        "note": "Use POST /webhook/survey-completion with real survey data for actual processing"
    })

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "Cell Products Survey Webhook Handler",
        "account": "Cell Products Only",
        "location_id": CONFIG['cell_products_location_id']
    })

def setup_logging_directory():
    """Ensure logs directory exists."""
    log_dir = "/Users/timothywade/Jarvis/logs"
    os.makedirs(log_dir, exist_ok=True)

def verify_configuration():
    """Verify Cell Products configuration is valid."""
    logging.info("🔧 Verifying Cell Products configuration...")
    
    # Test API key validity
    headers = {
        "Authorization": f"Bearer {CONFIG['company_api_key']}",
        "Content-Type": "application/json",
        "Version": "2021-07-28"
    }
    
    try:
        response = requests.get(f"{CONFIG['base_url']}/locations/", headers=headers)
        if response.status_code == 200:
            logging.info("✅ Cell Products API key is valid")
            return True
        else:
            logging.error(f"❌ Cell Products API key invalid: {response.status_code}")
            return False
    except Exception as e:
        logging.error(f"❌ Configuration verification failed: {e}")
        return False

if __name__ == '__main__':
    
    # Get port from environment variable (for cloud deployment) or use default
    port = int(os.environ.get('PORT', 8080))
    host = os.environ.get('HOST', '0.0.0.0')  # 0.0.0.0 for cloud deployment
    
    logging.info("🚀 Starting Cell Products Survey Webhook Handler")
    logging.info("=" * 60)
    logging.info(f"🏢 Account: Cell Products (ID: {CONFIG['cell_products_location_id']})")
    logging.info("📡 Listening for survey completion webhooks")
    logging.info(f"🔗 Endpoint: http://{host}:{port}/webhook/survey-completion")
    logging.info(f"🧪 Test endpoint: http://{host}:{port}/webhook/test")
    logging.info(f"❤️ Health check: http://{host}:{port}/health")
    
    # Skip API verification for now - start server directly
    logging.info("✅ Starting server without API verification")
    app.run(host=host, port=port, debug=False)  # debug=False for production