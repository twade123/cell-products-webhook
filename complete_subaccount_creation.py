#!/usr/bin/env python3
"""
Webhook-driven sub-account creation system for Cell Products account.
Listens for survey completion webhooks and automatically creates sub-accounts.
STANDALONE VERSION - Uses environment variables directly.
"""

import requests
import json
import logging
import os
from datetime import datetime
from flask import Flask, request, jsonify
import traceback

# Configuration using environment variables
CONFIG = {
    # Get API key from environment variable
    'company_api_key': os.environ.get('GHL_API_KEY', ''),
    
    # Cell Products Location ID from environment variable
    'cell_products_location_id': os.environ.get('GHL_LOCATION_ID', '10SapwdFnQK3Kwqp5ecv'),
    
    # API Configuration
    'base_url': os.environ.get('GHL_BASE_URL', 'https://rest.gohighlevel.com/v1'),
    'webhook_auth_token': 'cell-products-survey-webhook-2025',
    
    # Default timezone for new sub-accounts
    'default_timezone': 'America/Phoenix'  # Cell Products is in Nevada/Arizona timezone
}

# Validate configuration
if not CONFIG['company_api_key']:
    print("❌ ERROR: GHL_API_KEY environment variable is required")
    print("Set it in your Railway dashboard under Variables")
    exit(1)

print("✅ Loaded Cell Products configuration from environment variables")
print(f"🏢 Company: cell_products")
print(f"📍 Location ID: {CONFIG['cell_products_location_id']}")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()  # Only console logging for cloud deployment
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
    # TEMPORARY FIX: Allow both location IDs while we debug the mismatch
    valid_location_ids = [
        CONFIG['cell_products_location_id'],  # Original expected ID
        'Sqbexj54nvsxOI4V7SsD'               # Actual incoming ID from GHL
    ]
    
    if source_location_id not in valid_location_ids:
        logging.error(f"❌ Unauthorized source location: {source_location_id}")
        logging.error(f"   Expected Cell Products IDs: {valid_location_ids}")
        return False
    
    if source_location_id != CONFIG['cell_products_location_id']:
        logging.warning(f"⚠️ Using alternate Cell Products location ID: {source_location_id}")
        logging.warning(f"   Expected: {CONFIG['cell_products_location_id']}")
    else:
        logging.info("✅ Webhook confirmed from Cell Products account")
    
    return True

def create_subaccount_from_survey_data(survey_data):
    """Create a new sub-account using survey submission data."""
    
    try:
        # Extract required data from survey - handle multiple possible field names
        business_name = (survey_data.get('business_name') or 
                        survey_data.get('businessName') or 
                        survey_data.get('company') or 
                        survey_data.get('companyName') or 
                        survey_data.get('Provider Name') or 
                        survey_data.get('Legal Company Name') or '').strip()
        
        first_name = (survey_data.get('first_name') or 
                     survey_data.get('firstName') or 
                     survey_data.get('fname') or 
                     survey_data.get('Patient First Name') or '').strip()
        
        last_name = (survey_data.get('last_name') or 
                    survey_data.get('lastName') or 
                    survey_data.get('lname') or 
                    survey_data.get('Patient Last Name') or '').strip()
        
        email = (survey_data.get('email') or 
                survey_data.get('emailAddress') or 
                survey_data.get('Email') or 
                survey_data.get('Patient Email') or '').strip()
        
        phone = (survey_data.get('phone') or 
                survey_data.get('phoneNumber') or 
                survey_data.get('mobile') or 
                survey_data.get('Phone') or 
                survey_data.get('Patient Phone') or '').strip()
        
        # Validate required fields
        if not all([business_name, first_name, last_name, email]):
            raise ValueError("Missing required fields: business_name, first_name, last_name, email")
        
        # Clean phone number
        clean_phone = phone.replace('+1', '').replace('-', '').replace('(', '').replace(')', '').replace(' ', '')
        
        # Build sub-account data
        subaccount_data = {
          "name": f"{business_name} - {first_name} {last_name}",
          "businessName": business_name,  # Required field
          "address": survey_data.get('address', ''),
          "city": survey_data.get('city', ''),
          "state": survey_data.get('state', ''),
          "postalCode": survey_data.get('zip_code', ''),
          "country": "US",
          "phone": clean_phone,
          "email": email,
          "website": survey_data.get('website', ''),
          "timezone": CONFIG['default_timezone'],
          "firstName": first_name,
          "lastName": last_name
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
        # GHL can send form fields nested in objects OR directly at top level
        survey_data = (payload.get('submission', {}) or 
                      payload.get('survey_data', {}) or 
                      payload.get('data', {}) or 
                      payload.get('contact', {}) or 
                      payload)  # Fallback to top-level payload if no nested structure
        
        survey_id = (payload.get('formId') or 
                    payload.get('survey_id') or 
                    payload.get('id', ''))
        
        # Validate survey data
        if not survey_data:
            logging.error("❌ No survey data in webhook")
            return jsonify({"error": "No survey data"}), 400
        
        # Debug: Log all available field names for troubleshooting
        logging.info(f"📊 Available survey fields: {list(survey_data.keys())}")
        logging.info(f"📊 Survey data sample: {dict(list(survey_data.items())[:10])}")  # First 10 fields
        
        business_name = (survey_data.get('business_name') or 
                        survey_data.get('businessName') or 
                        survey_data.get('company') or 
                        survey_data.get('companyName') or 
                        survey_data.get('Provider Name') or 
                        survey_data.get('Legal Company Name') or '').strip()
        
        if not business_name:
            logging.error("❌ Business name required for sub-account creation")
            return jsonify({"error": "Business name required"}), 400
        
        # Log processing start - extract names properly
        first_name_field = (survey_data.get('first_name') or 
                           survey_data.get('firstName') or 
                           survey_data.get('fname') or 
                           survey_data.get('Patient First Name') or '')
        last_name_field = (survey_data.get('last_name') or 
                          survey_data.get('lastName') or 
                          survey_data.get('lname') or 
                          survey_data.get('Patient Last Name') or '')
        contact_name = f"{first_name_field} {last_name_field}".strip()
        logging.info(f"🚀 Processing survey completion for: {contact_name}")
        logging.info(f"🏢 Business: {business_name}")
        logging.info(f"📝 Survey ID: {survey_id}")
        logging.info(f"📍 Source: Cell Products ({source_location_id})")
        
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
        "location_id": CONFIG['cell_products_location_id'],
        "api_key_configured": bool(CONFIG['company_api_key'])
    })

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
    
    # Verify configuration before starting
    if verify_configuration():
        logging.info("✅ Configuration verified - starting server")
        app.run(host=host, port=port, debug=False)  # debug=False for production
    else:
        logging.error("❌ Configuration verification failed - server not started")
