
PROJECT TITLE:
AI-Powered Multimodal Retail Automation and Predictive Business Intelligence System

COLLEGE:
Canara Engineering College, Benjanapadavu, Mangaluru - 574218
Department of Artificial Intelligence and Machine Learning

TEAM NUMBER:
Team 07

TEAM MEMBERS AND USN:
1. Ananya Hebbar       USN: 4CB23AI011
2. P Harshitha         USN: 4CB23AI064
3. Abhijna V N         USN: 4CB23AI005


PROJECT INSTALLATION LOCATION:
AIL06 – Intelligent Systems Laboratory
System Number: 

================================================================================
PROJECT OVERVIEW
================================================================================
This repository contains the complete implementation of an AI-powered retail
automation and predictive business intelligence system designed for small-scale
retail businesses. The platform enables multiple shop owners and customers to
register using Firebase Phone Authentication, manage independent retail stores,
process chatbot-assisted customer orders from text and handwritten images,
generate Razorpay QR code payments, monitor inventory in real time, and
forecast future product demand using Artificial Intelligence and Machine
Learning.

================================================================================
FEATURES
================================================================================
- Role-based Firebase Phone Authentication
- Multiple shop owner and customer registration
- Multi-store retail management
- AI-powered handwritten grocery list OCR using Tesseract OCR
- NLP-based product information extraction using spaCy NER
- Fuzzy product catalog matching using difflib
- Chatbot-assisted order placement
- Product and inventory management
- Razorpay QR code payment integration
- Real-time WebSocket notifications
- Demand forecasting using Meta Prophet
- PostgreSQL database integration
- FastAPI backend with React (Vite) frontend
- React Native (Expo) mobile application

================================================================================
PROJECT STRUCTURE
================================================================================
retail_automation_project/
├── backend/
│   ├── app/
│   │   ├── ml_models/
│   │   │   ├── prophet_final_models.pkl
│   │   │   └── Retail_NER_Model.pkl
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── ocr_service.py
│   │   │   ├── nlp_service.py
│   │   │   ├── matching_service.py
│   │   │   └── forecast_service.py
│   │   ├── routers/
│   │   │   ├── __init__.py
│   │   │   ├── auth.py
│   │   │   ├── shop.py
│   │   │   ├── product.py
│   │   │   ├── order.py
│   │   │   ├── payment.py
│   │   │   ├── forecast.py
│   │   │   ├── alert.py
│   │   │   └── chat.py
│   │   ├── __init__.py
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── models.py
│   │   ├── schemas.py
│   │   └── websocket_manager.py
│   ├── models/
│   │   ├── Retail_NER_Model.pkl
│   │   └── retail_ner/
│   ├── .env.example
│   ├── requirements.txt
│   ├── run.py
│   ├── seed_database.py
│   ├── test_auth_flows.py
│   ├── test_complete_order_flow.py
│   └── test_razorpay_flow.py
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── Login.jsx
│   │   │   ├── ChatBot.jsx
│   │   │   ├── OwnerDashboard.jsx
│   │   │   └── OwnerRegister.jsx
│   │   ├── utils/
│   │   │   └── dateTimeUtils.js
│   │   ├── App.jsx
│   │   ├── firebaseConfig.js
│   │   ├── main.jsx
│   │   └── index.css
│   ├── index.html
│   ├── package.json
│   └── vite.config.js
├── mobile/
│   ├── screens/
│   │   ├── tabs/
│   │   ├── CustomerChatScreen.js
│   │   ├── LoginScreen.js
│   │   ├── OwnerDashboardScreen.js
│   │   └── OwnerRegisterScreen.js
│   ├── App.js
│   ├── app.json
│   └── package.json
├── nlp_dataset_scripts/
├── sales_data_seed.csv
├── Retail_NLP_Training_Dataset.jsonl
├── Retail_NLP_Training_Dataset_Excel.xlsx
├── items list images.zip
├── .gitignore
└── Readme.txt

================================================================================
DATASETS USED & SOURCES
================================================================================
1. Sales History Dataset:
   - File: sales_data_seed.csv
   - Source: Synthetically generated historical sales transactions
   - Duration: 90 Days
   - Records: 161,000 sales transactions across 1,000 retail catalog items
   - Features: product_id, product_name, unit, quantity, price, sold_at
   - Details: Contains daily sales records, weekly seasonal demand variations,
     random fluctuations, and product-specific demand patterns. Used for
     database seeding and Meta Prophet time-series demand forecasting.

2. Newly Generated Dataset (Retail NLP Training Dataset):
   - Files: Retail_NLP_Training_Dataset.jsonl & Retail_NLP_Training_Dataset_Excel.xlsx
   - Source: Newly generated and audited domain-specific dataset (generated via
     nlp_dataset_scripts/generate_dataset.py)
   - Records: 3,152 annotated grocery order samples
   - Format: JSON Lines with character span offsets and entity tags
   - Features: text, entities (PRODUCT, QUANTITY, UNIT)
   - Details: Custom created and verified to train the project's domain-specific
     spaCy Named Entity Recognition (NER) model (Retail_NER_Model.pkl).

3. Sample Handwritten Grocery Lists:
   - File: items list images.zip
   - Source: Collected real-world handwritten grocery lists
   - Details: Scanned and photographed notes used to benchmark and evaluate
     the Tesseract OCR image preprocessing and text recognition pipeline.

================================================================================
TECHNOLOGY STACK & OFFICIAL DOWNLOAD / DOCUMENTATION LINKS
================================================================================
Frontend Technologies:
- React.js: https://react.dev/
- Vite: https://vitejs.dev/
- HTML5 & CSS3
- Firebase Authentication: https://firebase.google.com/docs/auth

Mobile Application:
- React Native: https://reactnative.dev/
- Expo: https://expo.dev/

Backend Technologies:
- FastAPI: https://fastapi.tiangolo.com/
- Python (v3.11.9): https://www.python.org/downloads/release/python-3119/
- Uvicorn: https://www.uvicorn.org/
- WebSockets: https://websockets.readthedocs.io/

Database Technologies:
- PostgreSQL: https://www.postgresql.org/download/windows/
- SQLAlchemy ORM: https://www.sqlalchemy.org/
- psycopg2-binary: https://www.psycopg.org/

AI / Machine Learning Technologies:
- Tesseract OCR (Windows UB-Mannheim): https://github.com/UB-Mannheim/tesseract/wiki
- spaCy (v3.7.5): https://spacy.io/
- Meta Prophet: https://facebook.github.io/prophet/
- Python difflib: https://docs.python.org/3/library/difflib.html

Payment Integration:
- Razorpay Payments API: https://razorpay.com/docs/api/

================================================================================
INSTALLATION PREREQUISITES
================================================================================
- Python 3.10 or later (Python 3.11.9 recommended)
- Node.js (v18 or later) & npm
- PostgreSQL (v15 or later)
- Tesseract OCR Engine installed to C:\Program Files\Tesseract-OCR

Database Initialization:
Create the PostgreSQL database in psql or pgAdmin:
CREATE DATABASE retail_automation;

================================================================================
BACKEND SETUP
================================================================================
1. Navigate to the backend directory:
   cd backend

2. Create and activate a virtual environment:
   python -m venv venv
   venv\Scripts\activate

3. Install dependencies:
   pip install -r requirements.txt
   pip install pytesseract
   python -m spacy download en_core_web_sm

4. Create .env file by copying .env.example:
   copy .env.example .env

5. Configure database credentials and settings in .env.

6. Seed the database:
   python seed_database.py

7. Run the FastAPI server:
   python run.py

   Backend runs at: http://127.0.0.1:8000
   API Docs: http://127.0.0.1:8000/docs

================================================================================
FRONTEND SETUP
================================================================================
1. Navigate to the frontend directory:
   cd frontend

2. Install dependencies:
   npm install

3. Run the development server:
   npm run dev

   Frontend runs at: http://localhost:5173

================================================================================
AUTHENTICATION
================================================================================
The application uses Firebase Phone Authentication with role-based login.

Shop Owner:
- Register/Login using phone number
- OTP verification
- Manage shop, products, inventory and orders
- View dashboard and forecasting

Customer:
- Register/Login using phone number
- OTP verification
- Select any available shop
- Place chatbot-assisted orders
- Complete Razorpay QR payments
- Receive real-time order updates

Developer Mode:
For local development and laboratory evaluation, a developer login bypass is
available when Firebase is not configured.

================================================================================
KEY FUNCTIONALITIES
================================================================================
- Multiple shop owners can register, create, and manage their retail shops.
- Multiple customers can register and place orders.
- Customers can select any available shop before placing an order.
- OCR extracts text from handwritten grocery lists.
- NLP extracts products, quantities and measurement units.
- Fuzzy matching maps extracted items to the shop catalog.
- Customers can review and modify generated orders.
- Razorpay QR payments support online transactions.
- Inventory updates automatically after successful orders.
- Shop owners receive real-time order notifications using WebSockets.
- Prophet forecasting predicts future product demand using historical sales data.

================================================================================
DEMAND FORECASTING
================================================================================
The forecasting module uses Meta Prophet to predict future product demand
based on historical sales data.

The model is pre-trained using the included 90-day sales dataset
(sales_data_seed.csv) and generates demand forecasts for 7, 14, and 30-day
inventory planning.

================================================================================
ENVIRONMENT VARIABLES (.env)
================================================================================

Create a .env file inside the backend directory.

Required variables:

DATABASE_URL=
JWT_SECRET=
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440
ENVIRONMENT=development
CORS_ORIGINS=
RAZORPAY_KEY_ID=
RAZORPAY_KEY_SECRET=
RAZORPAY_WEBHOOK_SECRET=
FIREBASE_PROJECT_ID=
FIREBASE_SERVICE_ACCOUNT_JSON=

================================================================================
FUTURE IMPROVEMENTS
================================================================================
- Email notifications
- Advanced analytics dashboard
- Sales reports
- Cloud deployment
================================================================================
