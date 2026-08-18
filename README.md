# AI-Powered Multimodal Retail Automation and Predictive Business Intelligence System

This repository contains the complete implementation of an AI-powered retail automation and predictive business intelligence system designed for small-scale retail businesses. The platform enables multiple shop owners and customers to register using Firebase Phone Authentication, manage independent retail stores, process chatbot-assisted customer orders from text and handwritten images, generate Razorpay QR code payments, monitor inventory in real time, and forecast future product demand using Artificial Intelligence and Machine Learning.

---

# Features

- Role-based Firebase Phone Authentication
- Multiple shop owner and customer registration
- Multi-store retail management
- AI-powered handwritten invoice OCR using Microsoft TrOCR
- NLP-based product information extraction using spaCy
- Fuzzy product catalog matching
- Chatbot-assisted order placement
- Product and inventory management
- Razorpay QR code payment integration
- Real-time WebSocket notifications
- Demand forecasting using Meta Prophet
- PostgreSQL database integration
- FastAPI backend with React (Vite) frontend

---

# Project Structure

```text
retail_automation_project/
├── backend/
│   ├── app/
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
│   │   │   └── alert.py
│   │   ├── __init__.py
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── models.py
│   │   ├── schemas.py
│   │   └── websocket_manager.py
│   ├── .env.example
│   ├── requirements.txt
│   ├── run.py
│   └── seed_database.py
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── Login.jsx
│   │   │   ├── ChatBot.jsx
│   │   │   └── OwnerDashboard.jsx
│   │   ├── App.jsx
│   │   ├── firebaseConfig.js
│   │   ├── main.jsx
│   │   └── index.css
│   ├── index.html
│   ├── package.json
│   └── vite.config.js
├── seed_dataset_generator.py
├── sales_data_seed.csv
├── .gitignore
└── README.md
```

---

# Sales History Dataset

The repository includes a synthetic historical sales dataset:

* **File:** `sales_data_seed.csv`
* **Duration:** 90 Days
* **Products:** Rice, Milk, Soap, Sugar and Apple

The dataset contains:

* Daily sales records
* Weekly seasonal demand variations
* Random sales fluctuations
* Product-specific demand patterns

This dataset is used for training and generating demand forecasts using the Meta Prophet forecasting model.

---

# Technology Stack

## Frontend

* React.js
* Vite
* HTML
* CSS
* Firebase Authentication

## Backend

* FastAPI
* Python

## Database

* PostgreSQL
* SQLAlchemy

## AI / Machine Learning

* Microsoft TrOCR
* spaCy
* Meta Prophet
* FuzzyWuzzy

## Payment

* Razorpay QR Payments

---

# Installation

## Prerequisites

* Python 3.10 or later
* Node.js (v18 or later)
* PostgreSQL

Create the PostgreSQL database:

```sql
CREATE DATABASE retail_automation;
```

---

# Backend Setup

Navigate to the backend directory.

```bash
cd backend
```

Install dependencies.

```bash
pip install -r requirements.txt
```

Create a `.env` file by copying `.env.example`.

Configure the required environment variables.

Seed the database.

```bash
python seed_database.py
```

Run the FastAPI server.

```bash
python run.py
```

Backend runs at:

```
http://127.0.0.1:8000
```

---

# Frontend Setup

Navigate to the frontend directory.

```bash
cd frontend
```

Install dependencies.

```bash
npm install
```

Run the development server.

```bash
npm run dev
```

Frontend runs at:

```
http://localhost:5173
```

---

# Authentication

The application uses Firebase Phone Authentication with role-based login.

### Shop Owner

- Register/Login using phone number
- OTP verification
- Manage shop, products, inventory and orders
- View dashboard and forecasting

### Customer

- Register/Login using phone number
- OTP verification
- Select any available shop
- Place chatbot-assisted orders
- Complete Razorpay QR payments
- Receive real-time order updates

### Developer Mode

For local development, a developer login bypass is available when Firebase is not configured.

---

# Key Functionalities

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

---

# Forecasting

The forecasting module uses **Meta Prophet** to predict future product demand based on historical sales data.

The model is trained using the included 90-day sales dataset and generates demand forecasts for inventory planning.

---

# Environment Variables

Create a `.env` file inside the backend directory.

Example:

```env
DATABASE_URL=

JWT_SECRET=

JWT_ALGORITHM=HS256

ACCESS_TOKEN_EXPIRE_MINUTES=1440

RAZORPAY_KEY_ID=

RAZORPAY_KEY_SECRET=

RAZORPAY_WEBHOOK_SECRET=

FIREBASE_PROJECT_ID=

FIREBASE_SERVICE_ACCOUNT_JSON=
```

---

# Future Improvements

- Email notifications
- Advanced analytics dashboard
- Inventory alerts
- Sales reports
- Cloud deployment
- Mobile application

---

