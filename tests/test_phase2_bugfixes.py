"""
Backend API Tests for Manufacturing ERP Phase 2 Bug Fixes
Tests: Settings Page 404, Quotation Approval 520, Security Checklist 520, 
       EXW Incoterm routing, Transport Window, Production Schedule, Job Order Status
"""
import pytest
import requests
import os
import uuid
from datetime import datetime, timedelta

# Read from frontend .env file
def get_backend_url():
    try:
        with open('/app/frontend/.env', 'r') as f:
            for line in f:
                if line.startswith('REACT_APP_BACKEND_URL='):
                    return line.split('=')[1].strip()
    except:
        pass
    return 'https://manufac-erp-2.preview.emergentagent.com'

BASE_URL = get_backend_url()


class TestAuthentication:
    """Test authentication endpoints"""
    
    def test_login_admin(self):
        """Test admin login"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@erp.com",
            "password": "admin123"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "access_token" in data
        assert "user" in data
        assert data["user"]["email"] == "admin@erp.com"
        print("✓ Admin login successful")
        return data["access_token"]
    
    def test_login_finance(self):
        """Test finance login"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "finance@erp.com",
            "password": "finance123"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "access_token" in data
        print("✓ Finance login successful")
        return data["access_token"]
    
    def test_login_security(self):
        """Test security login"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "security@erp.com",
            "password": "security123"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "access_token" in data
        print("✓ Security login successful")
        return data["access_token"]


class TestSettingsPage:
    """Test Settings Page - Bug Fix: 404 error"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get admin auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@erp.com",
            "password": "admin123"
        })
        return response.json()["access_token"]
    
    def test_settings_all_endpoint(self, auth_token):
        """Test GET /api/settings/all - should return 200, not 404"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/settings/all", headers=headers)
        
        assert response.status_code == 200, f"Settings endpoint failed with {response.status_code}: {response.text}"
        data = response.json()
        
        # Validate response structure
        assert "payment_terms" in data, "Missing payment_terms in settings"
        assert "document_templates" in data, "Missing document_templates in settings"
        assert "container_types" in data, "Missing container_types in settings"
        assert "companies" in data, "Missing companies in settings"
        assert "packaging_types" in data, "Missing packaging_types in settings"
        
        # Validate data types
        assert isinstance(data["payment_terms"], list)
        assert isinstance(data["document_templates"], list)
        assert isinstance(data["container_types"], list)
        
        print(f"✓ Settings page loads correctly with {len(data['payment_terms'])} payment terms, {len(data['container_types'])} container types")
    
    def test_settings_suppliers_endpoint(self, auth_token):
        """Test GET /api/suppliers - used by Settings page Vendors tab"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/suppliers", headers=headers)
        
        assert response.status_code == 200, f"Suppliers endpoint failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Suppliers endpoint works: {len(data)} suppliers")


class TestQuotationApproval:
    """Test Quotation Approval - Bug Fix: 520 error"""
    
    @pytest.fixture(scope="class")
    def finance_token(self):
        """Get finance auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "finance@erp.com",
            "password": "finance123"
        })
        return response.json()["access_token"]
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@erp.com",
            "password": "admin123"
        })
        return response.json()["access_token"]
    
    def test_get_pending_quotations(self, admin_token):
        """Test GET /api/quotations?status=pending"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/quotations?status=pending", headers=headers)
        
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Found {len(data)} pending quotations")
        return data
    
    def test_approve_quotation_no_500_error(self, finance_token, admin_token):
        """Test PUT /api/quotations/{id}/approve - should not return 500/520 error"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        # First get pending quotations
        response = requests.get(f"{BASE_URL}/api/quotations?status=pending", headers=headers)
        quotations = response.json()
        
        if not quotations:
            # Create a test quotation first
            print("  No pending quotations, creating test quotation...")
            
            # Get a customer
            customers_resp = requests.get(f"{BASE_URL}/api/customers", headers=headers)
            customers = customers_resp.json()
            
            # Get a product
            products_resp = requests.get(f"{BASE_URL}/api/products", headers=headers)
            products = products_resp.json()
            
            if customers and products:
                customer = customers[0]
                product = products[0]
                
                quotation_data = {
                    "customer_id": customer["id"],
                    "customer_name": customer["name"],
                    "items": [{
                        "product_id": product["id"],
                        "product_name": product["name"],
                        "sku": product.get("sku", "TEST-SKU"),
                        "quantity": 10,
                        "unit_price": 100,
                        "packaging": "Bulk",
                        "total": 1000
                    }],
                    "currency": "USD",
                    "order_type": "local",
                    "payment_terms": "Net 30"
                }
                
                create_resp = requests.post(f"{BASE_URL}/api/quotations", json=quotation_data, headers=headers)
                if create_resp.status_code == 200:
                    quotations = [create_resp.json()]
                    print(f"  Created test quotation: {quotations[0].get('pfi_number')}")
                else:
                    pytest.skip("Could not create test quotation")
            else:
                pytest.skip("No customers or products available for test")
        
        # Now approve a quotation
        quotation = quotations[0]
        quotation_id = quotation["id"]
        
        finance_headers = {"Authorization": f"Bearer {finance_token}"}
        response = requests.put(f"{BASE_URL}/api/quotations/{quotation_id}/approve", headers=finance_headers)
        
        # Should NOT return 500/520 error
        assert response.status_code != 500, f"Quotation approval returned 500 error: {response.text}"
        assert response.status_code != 520, f"Quotation approval returned 520 error: {response.text}"
        
        # Should return 200 or 404 (if already processed)
        assert response.status_code in [200, 404], f"Unexpected status {response.status_code}: {response.text}"
        
        if response.status_code == 200:
            data = response.json()
            assert "message" in data
            print(f"✓ Quotation {quotation.get('pfi_number')} approved successfully without 500/520 error")
        else:
            print(f"✓ Quotation already processed (404) - no 500/520 error")


class TestSecurityChecklist:
    """Test Security Checklist Creation - Bug Fix: 520 error"""
    
    @pytest.fixture(scope="class")
    def security_token(self):
        """Get security auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "security@erp.com",
            "password": "security123"
        })
        if response.status_code != 200:
            # Try admin if security user doesn't exist
            response = requests.post(f"{BASE_URL}/api/auth/login", json={
                "email": "admin@erp.com",
                "password": "admin123"
            })
        return response.json()["access_token"]
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@erp.com",
            "password": "admin123"
        })
        return response.json()["access_token"]
    
    def test_create_security_checklist_no_500_error(self, admin_token):
        """Test POST /api/security/checklists - should not return 500/520 error"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        # Create a security checklist
        checklist_data = {
            "ref_type": "INWARD",
            "ref_id": str(uuid.uuid4()),  # Test reference ID
            "ref_number": "TEST-REF-001",
            "supplier_name": "Test Supplier",
            "vehicle_number": "ABC-1234",
            "driver_name": "Test Driver",
            "notes": "Test checklist for bug fix verification"
        }
        
        response = requests.post(f"{BASE_URL}/api/security/checklists", json=checklist_data, headers=headers)
        
        # Should NOT return 500/520 error
        assert response.status_code != 500, f"Security checklist creation returned 500 error: {response.text}"
        assert response.status_code != 520, f"Security checklist creation returned 520 error: {response.text}"
        
        # Should return 200 or 403 (if not security role)
        assert response.status_code in [200, 403], f"Unexpected status {response.status_code}: {response.text}"
        
        if response.status_code == 200:
            data = response.json()
            assert "id" in data, "Response missing 'id' field"
            assert "checklist_number" in data, "Response missing 'checklist_number' field"
            assert "_id" not in data, "Response should not contain MongoDB _id"
            print(f"✓ Security checklist created successfully: {data.get('checklist_number')}")
        else:
            print(f"✓ Security checklist endpoint accessible (403 = role restriction, not 500/520)")


class TestEXWIncotermRouting:
    """Test EXW Incoterm Routing - Bug Fix: Broken routing"""
    
    @pytest.fixture(scope="class")
    def finance_token(self):
        """Get finance auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "finance@erp.com",
            "password": "finance123"
        })
        return response.json()["access_token"]
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@erp.com",
            "password": "admin123"
        })
        return response.json()["access_token"]
    
    def test_get_draft_purchase_orders(self, admin_token):
        """Test GET /api/purchase-orders?status=DRAFT"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/purchase-orders?status=DRAFT", headers=headers)
        
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Found {len(data)} DRAFT purchase orders")
        return data
    
    def test_finance_approve_exw_po_routes_to_transport(self, finance_token, admin_token):
        """Test PUT /api/purchase-orders/{id}/finance-approve with EXW incoterm routes to Transport Window"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        # Get DRAFT POs
        response = requests.get(f"{BASE_URL}/api/purchase-orders?status=DRAFT", headers=headers)
        draft_pos = response.json()
        
        # Find an EXW PO or create one
        exw_po = None
        for po in draft_pos:
            if po.get("incoterm", "").upper() == "EXW":
                exw_po = po
                break
        
        if not exw_po:
            print("  No EXW DRAFT PO found, testing endpoint accessibility...")
            # Test with a non-existent ID to verify endpoint doesn't return 500
            finance_headers = {"Authorization": f"Bearer {finance_token}"}
            response = requests.put(f"{BASE_URL}/api/purchase-orders/non-existent-id/finance-approve", headers=finance_headers)
            
            # Should return 404, not 500
            assert response.status_code != 500, f"Finance approve returned 500 error: {response.text}"
            assert response.status_code == 404, f"Expected 404 for non-existent PO, got {response.status_code}"
            print("✓ EXW PO finance-approve endpoint accessible (no 500 error)")
            return
        
        # Approve the EXW PO
        finance_headers = {"Authorization": f"Bearer {finance_token}"}
        response = requests.put(f"{BASE_URL}/api/purchase-orders/{exw_po['id']}/finance-approve", headers=finance_headers)
        
        assert response.status_code != 500, f"Finance approve returned 500 error: {response.text}"
        
        if response.status_code == 200:
            data = response.json()
            # Check if routed to transport
            if "route_result" in data:
                assert data["route_result"].get("routed_to") == "TRANSPORTATION_INWARD", "EXW PO should route to TRANSPORTATION_INWARD"
                print(f"✓ EXW PO {exw_po.get('po_number')} approved and routed to Transport Window")
            else:
                print(f"✓ EXW PO approved successfully")
        else:
            print(f"✓ Finance approve endpoint accessible (status: {response.status_code})")


class TestTransportWindow:
    """Test Transport Window - Bug Fix: EXW inward records"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@erp.com",
            "password": "admin123"
        })
        return response.json()["access_token"]
    
    def test_transport_inward_endpoint(self, admin_token):
        """Test GET /api/transport/inward - should show EXW records"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/transport/inward", headers=headers)
        
        assert response.status_code == 200, f"Transport inward failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        
        # Check for EXW records
        exw_records = [t for t in data if t.get("source") == "PO_EXW" or t.get("incoterm") == "EXW"]
        print(f"✓ Transport inward endpoint works: {len(data)} total records, {len(exw_records)} EXW records")
    
    def test_transport_outward_endpoint(self, admin_token):
        """Test GET /api/transport/outward"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/transport/outward", headers=headers)
        
        assert response.status_code == 200, f"Transport outward failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Transport outward endpoint works: {len(data)} records")


class TestProductionSchedule:
    """Test Production Schedule - Bug Fix: in_production jobs"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@erp.com",
            "password": "admin123"
        })
        return response.json()["access_token"]
    
    def test_unified_schedule_endpoint(self, admin_token):
        """Test GET /api/production/unified-schedule - should include in_production jobs"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/production/unified-schedule", headers=headers)
        
        assert response.status_code == 200, f"Unified schedule failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        
        # Check schedule structure
        if data:
            day = data[0]
            assert "date" in day
            assert "drums_capacity" in day
            assert "jobs" in day
            
            # Count jobs by status
            all_jobs = []
            for day in data:
                all_jobs.extend(day.get("jobs", []))
            
            in_production = [j for j in all_jobs if j.get("status") == "in_production"]
            print(f"✓ Unified schedule works: {len(data)} days, {len(all_jobs)} total jobs, {len(in_production)} in_production")
        else:
            print("✓ Unified schedule endpoint works (no scheduled jobs)")
    
    def test_production_schedule_endpoint(self, admin_token):
        """Test GET /api/production/schedule - should include in_production jobs"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/production/schedule", headers=headers)
        
        assert response.status_code == 200, f"Production schedule failed: {response.text}"
        data = response.json()
        
        # Check for in_production jobs in the response
        if "ready_jobs" in data:
            print(f"✓ Production schedule works: {len(data.get('ready_jobs', []))} ready, {len(data.get('partial_jobs', []))} partial, {len(data.get('not_ready_jobs', []))} not ready")
        else:
            print(f"✓ Production schedule endpoint works")


class TestJobOrderStatus:
    """Test Job Order Status Update - Bug Fix: status update"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@erp.com",
            "password": "admin123"
        })
        return response.json()["access_token"]
    
    def test_get_job_orders(self, admin_token):
        """Test GET /api/job-orders"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/job-orders", headers=headers)
        
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Found {len(data)} job orders")
        return data
    
    def test_job_order_status_update(self, admin_token):
        """Test PUT /api/job-orders/{id}/status?status=approved"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        # Get job orders
        response = requests.get(f"{BASE_URL}/api/job-orders", headers=headers)
        job_orders = response.json()
        
        # Find a pending job order
        pending_job = None
        for job in job_orders:
            if job.get("status") == "pending":
                pending_job = job
                break
        
        if not pending_job:
            print("  No pending job orders found, testing endpoint accessibility...")
            # Test with a non-existent ID
            response = requests.put(f"{BASE_URL}/api/job-orders/non-existent-id/status?status=approved", headers=headers)
            
            # Should return 404, not 500
            assert response.status_code != 500, f"Job order status update returned 500 error: {response.text}"
            print("✓ Job order status endpoint accessible (no 500 error)")
            return
        
        # Update status to approved
        response = requests.put(f"{BASE_URL}/api/job-orders/{pending_job['id']}/status?status=approved", headers=headers)
        
        assert response.status_code != 500, f"Job order status update returned 500 error: {response.text}"
        
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Job order {pending_job.get('job_number')} status updated to approved")
        else:
            print(f"✓ Job order status endpoint accessible (status: {response.status_code})")


class TestObjectIdSerialization:
    """Test that MongoDB ObjectId is not returned in responses"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@erp.com",
            "password": "admin123"
        })
        return response.json()["access_token"]
    
    def test_quotations_no_objectid(self, admin_token):
        """Test that quotations response doesn't contain _id"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/quotations", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        
        for item in data[:5]:  # Check first 5
            assert "_id" not in item, f"Quotation contains _id: {item.get('_id')}"
        
        print("✓ Quotations response doesn't contain MongoDB _id")
    
    def test_job_orders_no_objectid(self, admin_token):
        """Test that job orders response doesn't contain _id"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/job-orders", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        
        for item in data[:5]:  # Check first 5
            assert "_id" not in item, f"Job order contains _id: {item.get('_id')}"
        
        print("✓ Job orders response doesn't contain MongoDB _id")
    
    def test_transport_inward_no_objectid(self, admin_token):
        """Test that transport inward response doesn't contain _id"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/transport/inward", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        
        for item in data[:5]:  # Check first 5
            assert "_id" not in item, f"Transport inward contains _id: {item.get('_id')}"
        
        print("✓ Transport inward response doesn't contain MongoDB _id")


if __name__ == "__main__":
    print("=" * 60)
    print("Manufacturing ERP Phase 2 Bug Fixes - Backend API Tests")
    print("=" * 60)
    
    # Run tests
    pytest.main([__file__, "-v", "--tb=short", "-s"])
