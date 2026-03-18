# Product Requirements Document (PRD)
**Project Name:** SafeTicket IL (MVP)
**Date:** December 16, 2025
**Version:** 1.3 (Final MVP Scope)

---

## 1. Project Overview

### 1.1. The Concept
A secure, C2C (Consumer-to-Consumer) marketplace for buying and selling second-hand event tickets. The platform focuses on safety, trust, and fair pricing.

### 1.2. The Problem
* **Trust:** Buyers in social media groups are frequently scammed (fake tickets, duplicate sales).
* **Cost:** Existing international resale platforms charge excessive fees.
* **Scalping:** Sellers often try to sell tickets for 2x or 3x the original price.

### 1.3. The Solution
A "Safe Marketplace" based on an **Escrow Model**.
* **Safety:** The platform holds the buyer's money and only releases it to the seller **after** the event takes place successfully.
* **Fairness:** Technical and community measures to ensure tickets are sold at or near Face Value.

---

## 2. Technical Stack (Strict Requirements)
*The developer must use the following technologies:*

* **Backend:** Python 3.10+ using **Django Framework** (Django REST Framework for API).
* **Frontend:** **React.js** (Modern functional components with Hooks).
* **Database:** PostgreSQL.
* **Code Repository:** Private **GitHub** repository (Client owns the code).
* **Payment Gateway:** Integration with an Israeli provider (e.g., Cardcom, Meshulam - API docs will be provided).

---

## 3. User Roles
1.  **Guest (Buyer):** Can browse listings and **BUY** tickets without creating a password/account. Must provide an Email Address for ticket delivery.
2.  **Registered User:** Can act as both a Buyer (with order history) and a Seller. *Note: Selling requires full registration and bank details.*
3.  **Admin (Superuser):** Has full access to the Dashboard to manage users, listings, and financial disputes.

---

## 4. Functional Requirements (User Stories)

### 4.1. Authentication & Profile
* **Sign Up/Login:** Users can register via Email/Password or Google Auth.
* **Bank Details (Seller Only):** Secure storage of bank account details (IBAN/Branch) required for receiving payouts.

### 4.2. Seller Flow (Listing a Ticket)
* **Create Listing:** A form to upload a ticket.
    * *Fields:* Event Name, Date & Time, Venue, Seat/Row (optional), Original Price (Face Value), Asking Price.
    * *Upload:* Seller must upload the **PDF Ticket**.
* **Price Logic:** The system must visually warn or technically prevent the user from entering an "Asking Price" significantly higher than the "Original Price".
* **Dashboard:** Seller can see the status of their tickets ("Active", "Sold", "Pending Payout", "Paid Out").

### 4.3. Buyer Flow (Purchasing)
* **Browse/Search:** Filter tickets by Event Name, Date, or Category.
* **Ticket Page:** View details (Price, Date, Location). Specific Seat Number and the PDF file are **hidden** until purchase.
* **"Report Listing" Button:** A button on every ticket page allowing users to flag a listing as "Overpriced" or "Suspicious". High report counts alert the Admin.
* **Checkout Process:**
    * Support for **Guest Checkout** (Email + Credit Card only).
    * Support for Registered User Checkout.
* **Delivery:** Immediately after successful payment, the system sends the PDF ticket to the buyer's email address.

### 4.4. Admin Panel (Back-Office)
* **Listing Verification:** The Admin view must display the **Entered Price** next to a **"Preview PDF"** button. This allows the Admin to quickly open the file and verify the Face Value.
* **Dispute Management:** A specific interface to "Refund Buyer" (cancel the transaction and return money to the buyer's card).
* **User Management:** View/Ban users.

---

## 5. Core Business Logic (The Escrow Engine)

This is the most critical part of the system's logic:

1.  **Money Holding:** When a purchase is made, funds are **NOT** transferred to the Seller. They are held in the Platform's merchant account (Escrow).
2.  **Payout Trigger:**
    * The system must have a scheduled job (Cron Job) that runs daily.
    * It checks for events that ended **24 hours ago**.
    * If no dispute was opened by the Buyer, the system marks the transaction as "Approved for Payout."
3.  **Dispute Window:** Buyers have exactly 24 hours after the event start time to report a problem via a specific link.
    * *If reported:* The Payout is frozen until Admin review.
    * *If not reported:* Payout proceeds automatically.

---

## 6. Scope of Work (MVP)

### Included (In Scope)
* Responsive Web Design (Desktop & Mobile web).
* Guest Checkout functionality.
* PDF file handling and storage (Secure S3 or similar).
* Email notifications (Welcome, Item Sold, Ticket Purchased).
* Admin Verification Tools.

### Excluded (Out of Scope - Phase 2)
* Native Mobile Apps (iOS/Android).
* Chat system between Buyer and Seller.
* Automatic QR code/PDF parsing (OCR).
* User Rating/Review system.

---

## 7. Deliverables & Milestones

1.  **Milestone 1:** Project setup, Database Schema, User Authentication APIs.
2.  **Milestone 2:** Seller Flow (Frontend + Backend) & Admin Verification Panel.
3.  **Milestone 3:** Buyer Flow (Guest & Registered) & Payment Gateway Integration.
4.  **Milestone 4:** Business Logic Implementation (Escrow/Cron Jobs) & Testing.
5.  **Milestone 5:** Final QA, Bug fixes, and Deployment to Production Server.