#!/usr/bin/env python3
"""
Backend API Testing for ERP System
Tests the 4 new features: Production Scheduling, Blend Reports, PDF Generation, Email Notifications
"""

import requests
import json
import time
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

# Configuration
BASE_URL = "https://fabflow-3.preview.emergentagent.com/api"
TEST_EMAIL = "admin2@test.com"
TEST_PASSWORD = "password123"

class ERPTester:
    def __init__(self):
        self.session = requests.Session()
        self.token = None
        self.user_data = None
        self.test_data = {}
        
    def log(self, message: str, level: str = "INFO"):
        """Log test messages"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {level}: {message}")
        
    def login(self) -> bool:
        """Login and get authentication token"""
        try:
            response = self.session.post(f"{BASE_URL}/auth/login", json={
                "email": TEST_EMAIL,
                "password": TEST_PASSWORD
            })
            
            if response.status_code == 200:
                data = response.json()
                self.token = data["access_token"]
                self.user_data = data["user"]
                self.session.headers.update({"Authorization": f"Bearer {self.token}"})
                self.log(f"✅ Login successful as {self.user_data['name']} ({self.user_data['role']})")
                return True
            else:
                self.log(f"❌ Login failed: {response.status_code} - {response.text}", "ERROR")
                return False
        except Exception as e:
            self.log(f"❌ Login error: {str(e)}", "ERROR")
            return False
    
    def create_test_data(self) -> bool:
        """Create test data needed for testing"""
        try:
            self.log("📝 Creating test data...")
            
            # 1. Create a customer
            customer_data = {
                "name": "Test Manufacturing Co",
                "company": "Test Manufacturing Co Ltd",
                "email": "test@manufacturing.com",
                "phone": "+971501234567",
                "address": "Dubai Industrial Area",
                "country": "UAE",
                "tax_id": "TRN123456789",
                "customer_type": "local"
            }
            
            response = self.session.post(f"{BASE_URL}/customers", json=customer_data)
            if response.status_code == 200:
                self.test_data["customer"] = response.json()
                self.log(f"✅ Customer created: {self.test_data['customer']['id']}")
            else:
                self.log(f"❌ Customer creation failed: {response.status_code} - {response.text}", "ERROR")
                return False
            
            # 2. Create raw materials
            raw_materials = [
                {
                    "sku": "RM001",
                    "name": "Base Chemical A",
                    "description": "Primary base chemical",
                    "unit": "KG",
                    "price_usd": 5.50,
                    "price_aed": 20.20,
                    "category": "raw_material",
                    "min_stock": 100
                },
                {
                    "sku": "RM002", 
                    "name": "Additive B",
                    "description": "Chemical additive",
                    "unit": "KG",
                    "price_usd": 12.00,
                    "price_aed": 44.00,
                    "category": "raw_material",
                    "min_stock": 50
                }
            ]
            
            self.test_data["raw_materials"] = []
            for material in raw_materials:
                response = self.session.post(f"{BASE_URL}/products", json=material)
                if response.status_code == 200:
                    material_data = response.json()
                    self.test_data["raw_materials"].append(material_data)
                    self.log(f"✅ Raw material created: {material_data['sku']}")
                else:
                    self.log(f"❌ Raw material creation failed: {response.status_code} - {response.text}", "ERROR")
                    return False
            
            # 3. Create finished product
            product_data = {
                "sku": "FP001",
                "name": "Premium Chemical Blend",
                "description": "High-quality chemical blend for industrial use",
                "unit": "KG",
                "price_usd": 25.00,
                "price_aed": 92.00,
                "category": "finished_product",
                "min_stock": 20
            }
            
            response = self.session.post(f"{BASE_URL}/products", json=product_data)
            if response.status_code == 200:
                self.test_data["product"] = response.json()
                self.log(f"✅ Product created: {self.test_data['product']['sku']}")
            else:
                self.log(f"❌ Product creation failed: {response.status_code} - {response.text}", "ERROR")
                return False
            
            # 4. Add stock to raw materials via GRN
            grn_data = {
                "supplier": "Chemical Supplier LLC",
                "items": [
                    {
                        "product_id": self.test_data["raw_materials"][0]["id"],
                        "product_name": self.test_data["raw_materials"][0]["name"],
                        "sku": self.test_data["raw_materials"][0]["sku"],
                        "quantity": 500.0,
                        "unit": "KG"
                    },
                    {
                        "product_id": self.test_data["raw_materials"][1]["id"],
                        "product_name": self.test_data["raw_materials"][1]["name"],
                        "sku": self.test_data["raw_materials"][1]["sku"],
                        "quantity": 200.0,
                        "unit": "KG"
                    }
                ],
                "delivery_note": "DN-2024-001",
                "notes": "Test stock for production"
            }
            
            response = self.session.post(f"{BASE_URL}/grn", json=grn_data)
            if response.status_code == 200:
                self.test_data["grn"] = response.json()
                self.log(f"✅ GRN created: {self.test_data['grn']['grn_number']}")
            else:
                self.log(f"❌ GRN creation failed: {response.status_code} - {response.text}", "ERROR")
                return False
            
            return True
            
        except Exception as e:
            self.log(f"❌ Test data creation error: {str(e)}", "ERROR")
            return False
    
    def create_quotation_workflow(self) -> bool:
        """Create quotation and convert to sales order"""
        try:
            self.log("📋 Creating quotation workflow...")
            
            # Create quotation
            quotation_data = {
                "customer_id": self.test_data["customer"]["id"],
                "customer_name": self.test_data["customer"]["name"],
                "items": [
                    {
                        "product_id": self.test_data["product"]["id"],
                        "product_name": self.test_data["product"]["name"],
                        "sku": self.test_data["product"]["sku"],
                        "quantity": 100.0,
                        "unit_price": 25.00,
                        "packaging": "Bulk",
                        "total": 2500.00
                    }
                ],
                "currency": "USD",
                "order_type": "local",
                "payment_terms": "Cash",
                "validity_days": 30,
                "notes": "Test quotation for blend report testing"
            }
            
            response = self.session.post(f"{BASE_URL}/quotations", json=quotation_data)
            if response.status_code == 200:
                self.test_data["quotation"] = response.json()
                self.log(f"✅ Quotation created: {self.test_data['quotation']['pfi_number']}")
            else:
                self.log(f"❌ Quotation creation failed: {response.status_code} - {response.text}", "ERROR")
                return False
            
            # Approve quotation (this should trigger email notification)
            response = self.session.put(f"{BASE_URL}/quotations/{self.test_data['quotation']['id']}/approve")
            if response.status_code == 200:
                self.log("✅ Quotation approved (email notification should be triggered)")
            else:
                self.log(f"❌ Quotation approval failed: {response.status_code} - {response.text}", "ERROR")
                return False
            
            # Create sales order
            sales_order_data = {
                "quotation_id": self.test_data["quotation"]["id"],
                "expected_delivery_date": (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d"),
                "notes": "Test sales order for production"
            }
            
            response = self.session.post(f"{BASE_URL}/sales-orders", json=sales_order_data)
            if response.status_code == 200:
                self.test_data["sales_order"] = response.json()
                self.log(f"✅ Sales order created: {self.test_data['sales_order']['spa_number']}")
            else:
                self.log(f"❌ Sales order creation failed: {response.status_code} - {response.text}", "ERROR")
                return False
            
            return True
            
        except Exception as e:
            self.log(f"❌ Quotation workflow error: {str(e)}", "ERROR")
            return False
    
    def create_job_order(self) -> bool:
        """Create job order with BOM"""
        try:
            self.log("🏭 Creating job order...")
            
            job_order_data = {
                "sales_order_id": self.test_data["sales_order"]["id"],
                "product_id": self.test_data["product"]["id"],
                "product_name": self.test_data["product"]["name"],
                "quantity": 100.0,
                "bom": [
                    {
                        "product_id": self.test_data["raw_materials"][0]["id"],
                        "product_name": self.test_data["raw_materials"][0]["name"],
                        "sku": self.test_data["raw_materials"][0]["sku"],
                        "required_qty": 80.0,
                        "unit": "KG"
                    },
                    {
                        "product_id": self.test_data["raw_materials"][1]["id"],
                        "product_name": self.test_data["raw_materials"][1]["name"],
                        "sku": self.test_data["raw_materials"][1]["sku"],
                        "required_qty": 20.0,
                        "unit": "KG"
                    }
                ],
                "priority": "high",
                "notes": "Test job order for blend report testing"
            }
            
            response = self.session.post(f"{BASE_URL}/job-orders", json=job_order_data)
            if response.status_code == 200:
                self.test_data["job_order"] = response.json()
                self.log(f"✅ Job order created: {self.test_data['job_order']['job_number']}")
                return True
            else:
                self.log(f"❌ Job order creation failed: {response.status_code} - {response.text}", "ERROR")
                return False
                
        except Exception as e:
            self.log(f"❌ Job order creation error: {str(e)}", "ERROR")
            return False
    
    def test_production_scheduling(self) -> bool:
        """Test Production Scheduling API endpoints"""
        try:
            self.log("🏭 Testing Production Scheduling API...")
            
            # Test GET /api/production/schedule
            response = self.session.get(f"{BASE_URL}/production/schedule")
            if response.status_code == 200:
                schedule_data = response.json()
                
                # Verify response structure
                required_keys = ["summary", "ready_jobs", "partial_jobs", "not_ready_jobs"]
                if all(key in schedule_data for key in required_keys):
                    self.log("✅ Production schedule endpoint returns correct structure")
                    
                    # Verify summary structure
                    summary = schedule_data["summary"]
                    summary_keys = ["total_pending", "ready_to_produce", "partial_materials", "awaiting_procurement"]
                    if all(key in summary for key in summary_keys):
                        self.log("✅ Production schedule summary has correct structure")
                        self.log(f"   📊 Summary: {summary}")
                    else:
                        self.log("❌ Production schedule summary missing required keys", "ERROR")
                        return False
                        
                    # Check if our job order appears in the schedule
                    all_jobs = schedule_data["ready_jobs"] + schedule_data["partial_jobs"] + schedule_data["not_ready_jobs"]
                    job_found = any(job["job_id"] == self.test_data["job_order"]["id"] for job in all_jobs)
                    if job_found:
                        self.log("✅ Test job order found in production schedule")
                    else:
                        self.log("⚠️ Test job order not found in production schedule", "WARNING")
                        
                else:
                    self.log("❌ Production schedule response missing required keys", "ERROR")
                    return False
            else:
                self.log(f"❌ Production schedule endpoint failed: {response.status_code} - {response.text}", "ERROR")
                return False
            
            # Test GET /api/production/procurement-list
            response = self.session.get(f"{BASE_URL}/production/procurement-list")
            if response.status_code == 200:
                procurement_data = response.json()
                
                # Verify response structure
                required_keys = ["total_materials_needed", "procurement_list"]
                if all(key in procurement_data for key in required_keys):
                    self.log("✅ Procurement list endpoint returns correct structure")
                    self.log(f"   📊 Materials needed: {procurement_data['total_materials_needed']}")
                    
                    # Check procurement list items structure
                    if procurement_data["procurement_list"]:
                        first_item = procurement_data["procurement_list"][0]
                        item_keys = ["product_id", "product_name", "sku", "current_stock", "total_required", "total_shortage"]
                        if all(key in first_item for key in item_keys):
                            self.log("✅ Procurement list items have correct structure")
                        else:
                            self.log("❌ Procurement list items missing required keys", "ERROR")
                            return False
                else:
                    self.log("❌ Procurement list response missing required keys", "ERROR")
                    return False
            else:
                self.log(f"❌ Procurement list endpoint failed: {response.status_code} - {response.text}", "ERROR")
                return False
            
            return True
            
        except Exception as e:
            self.log(f"❌ Production scheduling test error: {str(e)}", "ERROR")
            return False
    
    def test_blend_reports_crud(self) -> bool:
        """Test Blend Reports CRUD API"""
        try:
            self.log("🧪 Testing Blend Reports CRUD API...")
            
            # First, update job order status to in_production (this should trigger email notification)
            response = self.session.put(f"{BASE_URL}/job-orders/{self.test_data['job_order']['id']}/status?status=in_production")
            if response.status_code == 200:
                self.log("✅ Job order status updated to in_production (email notification should be triggered)")
            else:
                self.log(f"❌ Job order status update failed: {response.status_code} - {response.text}", "ERROR")
                return False
            
            # Test GET /api/blend-reports (list all)
            response = self.session.get(f"{BASE_URL}/blend-reports")
            if response.status_code == 200:
                self.log("✅ Blend reports list endpoint working")
                initial_reports = response.json()
            else:
                self.log(f"❌ Blend reports list failed: {response.status_code} - {response.text}", "ERROR")
                return False
            
            # Test POST /api/blend-reports (create new)
            blend_report_data = {
                "job_order_id": self.test_data["job_order"]["id"],
                "batch_number": f"BATCH-{int(time.time())}",
                "blend_date": datetime.now().strftime("%Y-%m-%d"),
                "operator_name": "John Smith",
                "materials_used": [
                    {
                        "product_id": self.test_data["raw_materials"][0]["id"],
                        "product_name": self.test_data["raw_materials"][0]["name"],
                        "sku": self.test_data["raw_materials"][0]["sku"],
                        "batch_lot": "LOT-001",
                        "quantity_used": 80.0
                    },
                    {
                        "product_id": self.test_data["raw_materials"][1]["id"],
                        "product_name": self.test_data["raw_materials"][1]["name"],
                        "sku": self.test_data["raw_materials"][1]["sku"],
                        "batch_lot": "LOT-002",
                        "quantity_used": 20.0
                    }
                ],
                "process_parameters": {
                    "temperature": 25.5,
                    "mixing_time": 45,
                    "speed": 150,
                    "pressure": 1.2
                },
                "quality_checks": {
                    "viscosity": 12.5,
                    "ph": 7.2,
                    "density": 1.15,
                    "color": "Clear"
                },
                "output_quantity": 98.5,
                "yield_percentage": 98.5,
                "notes": "Test blend report for API testing"
            }
            
            response = self.session.post(f"{BASE_URL}/blend-reports", json=blend_report_data)
            if response.status_code == 200:
                self.test_data["blend_report"] = response.json()
                self.log(f"✅ Blend report created: {self.test_data['blend_report']['report_number']}")
            else:
                self.log(f"❌ Blend report creation failed: {response.status_code} - {response.text}", "ERROR")
                return False
            
            # Test GET /api/blend-reports/{id} (get single)
            response = self.session.get(f"{BASE_URL}/blend-reports/{self.test_data['blend_report']['id']}")
            if response.status_code == 200:
                report_data = response.json()
                self.log("✅ Blend report get single endpoint working")
                
                # Verify structure
                required_keys = ["id", "report_number", "job_number", "batch_number", "materials_used", "process_parameters", "quality_checks"]
                if all(key in report_data for key in required_keys):
                    self.log("✅ Blend report has correct structure")
                else:
                    self.log("❌ Blend report missing required keys", "ERROR")
                    return False
            else:
                self.log(f"❌ Blend report get single failed: {response.status_code} - {response.text}", "ERROR")
                return False
            
            # Test PUT /api/blend-reports/{id}/approve (approve report)
            response = self.session.put(f"{BASE_URL}/blend-reports/{self.test_data['blend_report']['id']}/approve")
            if response.status_code == 200:
                self.log("✅ Blend report approval endpoint working")
            else:
                self.log(f"❌ Blend report approval failed: {response.status_code} - {response.text}", "ERROR")
                return False
            
            return True
            
        except Exception as e:
            self.log(f"❌ Blend reports CRUD test error: {str(e)}", "ERROR")
            return False
    
    def test_pdf_generation(self) -> bool:
        """Test PDF Generation endpoints"""
        try:
            self.log("📄 Testing PDF Generation...")
            
            # Test GET /api/pdf/quotation/{id}
            response = self.session.get(f"{BASE_URL}/pdf/quotation/{self.test_data['quotation']['id']}")
            if response.status_code == 200:
                # Check if response is PDF
                content_type = response.headers.get('content-type', '')
                if 'application/pdf' in content_type:
                    self.log("✅ Quotation PDF generation working - correct content type")
                    
                    # Check content length
                    if len(response.content) > 1000:  # PDF should be substantial
                        self.log(f"✅ Quotation PDF has reasonable size: {len(response.content)} bytes")
                    else:
                        self.log("⚠️ Quotation PDF seems too small", "WARNING")
                else:
                    self.log(f"❌ Quotation PDF wrong content type: {content_type}", "ERROR")
                    return False
            else:
                self.log(f"❌ Quotation PDF generation failed: {response.status_code} - {response.text}", "ERROR")
                return False
            
            # Test GET /api/pdf/blend-report/{id}
            response = self.session.get(f"{BASE_URL}/pdf/blend-report/{self.test_data['blend_report']['id']}")
            if response.status_code == 200:
                # Check if response is PDF
                content_type = response.headers.get('content-type', '')
                if 'application/pdf' in content_type:
                    self.log("✅ Blend report PDF generation working - correct content type")
                    
                    # Check content length
                    if len(response.content) > 1000:  # PDF should be substantial
                        self.log(f"✅ Blend report PDF has reasonable size: {len(response.content)} bytes")
                    else:
                        self.log("⚠️ Blend report PDF seems too small", "WARNING")
                else:
                    self.log(f"❌ Blend report PDF wrong content type: {content_type}", "ERROR")
                    return False
            else:
                self.log(f"❌ Blend report PDF generation failed: {response.status_code} - {response.text}", "ERROR")
                return False
            
            return True
            
        except Exception as e:
            self.log(f"❌ PDF generation test error: {str(e)}", "ERROR")
            return False
    
    def test_email_notifications(self) -> bool:
        """Test Email Notifications (already triggered during workflow)"""
        try:
            self.log("📧 Testing Email Notifications...")
            
            # Email notifications were already triggered during:
            # 1. Quotation approval (in create_quotation_workflow)
            # 2. Job order status change (in test_blend_reports_crud)
            
            # We can test CRO received notification by creating a shipping booking
            self.log("🚢 Testing CRO received notification...")
            
            # Create shipping booking
            shipping_data = {
                "job_order_ids": [self.test_data["job_order"]["id"]],
                "shipping_line": "Test Shipping Line",
                "container_type": "20ft",
                "container_count": 1,
                "port_of_loading": "Jebel Ali",
                "port_of_discharge": "Hamburg",
                "cargo_description": "Chemical Products",
                "cargo_weight": 100.0,
                "is_dg": False,
                "notes": "Test shipping booking for email notification"
            }
            
            response = self.session.post(f"{BASE_URL}/shipping-bookings", json=shipping_data)
            if response.status_code == 200:
                shipping_booking = response.json()
                self.log(f"✅ Shipping booking created: {shipping_booking['booking_number']}")
                
                # Update with CRO details (this should trigger email notification)
                cro_data = {
                    "cro_number": f"CRO-{int(time.time())}",
                    "vessel_name": "Test Vessel",
                    "vessel_date": (datetime.now() + timedelta(days=15)).strftime("%Y-%m-%d"),
                    "cutoff_date": (datetime.now() + timedelta(days=10)).strftime("%Y-%m-%d"),
                    "freight_rate": 1500.0,
                    "freight_currency": "USD"
                }
                
                response = self.session.put(f"{BASE_URL}/shipping-bookings/{shipping_booking['id']}/cro", json=cro_data)
                if response.status_code == 200:
                    self.log("✅ CRO details updated (email notification should be triggered)")
                else:
                    self.log(f"❌ CRO update failed: {response.status_code} - {response.text}", "ERROR")
                    return False
            else:
                self.log(f"❌ Shipping booking creation failed: {response.status_code} - {response.text}", "ERROR")
                return False
            
            self.log("✅ Email notification tests completed (notifications are sent asynchronously)")
            return True
            
        except Exception as e:
            self.log(f"❌ Email notification test error: {str(e)}", "ERROR")
            return False
    
    def run_all_tests(self) -> Dict[str, bool]:
        """Run all tests and return results"""
        results = {}
        
        self.log("🚀 Starting ERP Backend API Tests...")
        self.log("=" * 60)
        
        # Login
        if not self.login():
            return {"login": False}
        results["login"] = True
        
        # Create test data
        if not self.create_test_data():
            return {**results, "test_data": False}
        results["test_data"] = True
        
        # Create quotation workflow
        if not self.create_quotation_workflow():
            return {**results, "quotation_workflow": False}
        results["quotation_workflow"] = True
        
        # Create job order
        if not self.create_job_order():
            return {**results, "job_order": False}
        results["job_order"] = True
        
        # Test Production Scheduling
        results["production_scheduling"] = self.test_production_scheduling()
        
        # Test Blend Reports CRUD
        results["blend_reports_crud"] = self.test_blend_reports_crud()
        
        # Test PDF Generation
        results["pdf_generation"] = self.test_pdf_generation()
        
        # Test Email Notifications
        results["email_notifications"] = self.test_email_notifications()
        
        return results

def main():
    """Main test function"""
    tester = ERPTester()
    results = tester.run_all_tests()
    
    print("\n" + "=" * 60)
    print("🏁 TEST RESULTS SUMMARY")
    print("=" * 60)
    
    total_tests = len(results)
    passed_tests = sum(1 for result in results.values() if result)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name.replace('_', ' ').title()}: {status}")
    
    print(f"\nOverall: {passed_tests}/{total_tests} tests passed")
    
    if passed_tests == total_tests:
        print("🎉 All tests passed!")
        return True
    else:
        print("⚠️ Some tests failed!")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)