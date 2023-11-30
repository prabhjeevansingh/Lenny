from flask import Flask, jsonify, request
import logging
from dotenv import load_dotenv
import os
from datetime import datetime
import requests
from urllib.parse import urlparse
from openai import OpenAI

load_dotenv() 

openai_api_key = os.environ.get('OPENAI_API_KEY')
if not openai_api_key:
    raise ValueError("Missing OPENAI_API_KEY environment variable")

client = OpenAI(
    api_key=openai_api_key
)

# Setting up logging
logging.basicConfig(level=logging.INFO)

# Initialize Flask app
app = Flask(__name__)

class LoanApprovalSystem:

    def format_url(self, url):
        '''Ensure the URL starts with http:// or https://.'''
        if not url.startswith(('http://', 'https://')):
            return 'https:' + url  # You can choose 'http://' based on your requirement
        return url
    

    def is_url(self, path):
        '''Check if the given path is a URL.'''
        try:
            result = urlparse(path)
            return all([result.scheme, result.netloc])
        except ValueError:
            return False
        
        

    def extract_from_files(self, json_data):
        '''Extract net salary and credit score from JSON data.'''
        gross_income = json_data.get('Monthly Gross Income', 0)
        credit_score = json_data.get('Credit Score', 0)

        return gross_income, credit_score

    def evaluate_application(self, application, json_data):
        '''Evaluate a loan application and return the decision along with the criteria evaluation.'''
        gross_income, credit_score = self.extract_from_files(json_data)
        dti = application['Total Monthly Debt Obligations'] / gross_income
        criteria_evaluation = {}
        rules_passed = 0

        criteria_evaluation['Debt-to-Income Ratio <= 0.43'] = dti <= 0.43
        criteria_evaluation['Credit Score >= 670'] = credit_score >= 670
        criteria_evaluation['Sector of Employment in Preferred List'] = application['Sector of Employment'] in ['Government Jobs', 'Healthcare', 'IT', 'Finance']
        criteria_evaluation['Number of Existing Loans < 5'] = application['Number of Existing Loans'] < 5
        criteria_evaluation['Loan Amount <= 60% of Annual Income'] = application['Desired Loan Amount'] <= 0.6 * (12 * gross_income)
        criteria_evaluation['Duration at Current Job >= 2 Years'] = application['Duration at Current Job'] >= 2
        criteria_evaluation['No History of Bankruptcy'] = application['History of Bankruptcy'] == 'No'

        birth_date = datetime.strptime(application['Date of Birth'], '%d/%m/%Y')
        age = datetime.now().year - birth_date.year
        criteria_evaluation['Age Between 18 and 70'] = 18 <= age <= 70
        criteria_evaluation['Residency Status as Permanent Resident or Citizen'] = application['Residency Status'] in ['Permanent Resident', 'Citizen']

        for key, value in criteria_evaluation.items():
            if value:
                rules_passed += 1

        decision = 'Approved' if rules_passed >= 8 else 'Declined'
        return decision, criteria_evaluation
    
    def generate_explanation(self, application, decision, criteria_evaluation):
        """Generate a concise, three-sentence explanation for the loan decision using gpt-3.5-turbo-instruct."""
        criteria_details = "\n".join([f"- {criterion}: {'Met' if met else 'Not Met'}" for criterion, met in criteria_evaluation.items()])
        prompt = f"""
        Based on the following criteria evaluation, provide a concise, three-sentence explanation for why this specific loan application was {decision.lower()}.
        Decision: {decision}. 
        Application details: {application}
        Criteria evaluation:
        {criteria_details}
        """

        try:
            response = client.completions.create(
                model="gpt-3.5-turbo-instruct",
                prompt=prompt,
                max_tokens=150  # Adjust as needed
            )
            explanation = response.choices[0].text.strip()
            # Split the response into sentences and take the first three
            explanation_sentences = explanation.split('. ')
            concise_explanation = '. '.join(explanation_sentences[:3]) + '.'
            return concise_explanation
        except Exception as e:
            logging.error(f"Error generating explanation: {e}")
            return "Explanation not available"

    def process_application(self, application):
        '''Process a single loan application.'''
        decision, criteria_evaluation = self.evaluate_application(application, application)
        explanation = self.generate_explanation(application, decision, criteria_evaluation)
        return {'application_id': application['_id'], 'result': decision, 'explanation': explanation}


@app.route('/')
def home():
    return 'Welcome to my Loan Approval Bot!'


@app.route('/process-entry', methods=['POST'])
def process_entry():
    '''API endpoint to receive and process POST data.'''
    try:
        # Receiving JSON data from the POST request
        entry_data = request.json['response']
        logging.info(f"Received data: {entry_data}")

        # Processing the data using LoanApprovalSystem
        loan_system = LoanApprovalSystem()
        processed_data = loan_system.process_application(entry_data)
        
        # Returning the processed data as JSON
        return jsonify(result=processed_data), 200
    except Exception as e:
        logging.error(f"Error in processing entry: {e}")
        return jsonify(error=str(e)), 500

# Run the Flask app if this file is executed directly
if __name__ == '__main__':
    app.run(debug=True)
