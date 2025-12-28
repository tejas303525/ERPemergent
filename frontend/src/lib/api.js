import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API_BASE = `${BACKEND_URL}/api`;

const api = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add auth token to requests
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('erp_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Handle auth errors
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('erp_token');
      localStorage.removeItem('erp_user');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

// Auth
export const authAPI = {
  login: (data) => api.post('/auth/login', data),
  register: (data) => api.post('/auth/register', data),
  getMe: () => api.get('/auth/me'),
};

// Customers
export const customerAPI = {
  getAll: () => api.get('/customers'),
  getOne: (id) => api.get(`/customers/${id}`),
  create: (data) => api.post('/customers', data),
};

// Products
export const productAPI = {
  getAll: (category) => api.get('/products', { params: { category } }),
  getOne: (id) => api.get(`/products/${id}`),
  create: (data) => api.post('/products', data),
  update: (id, data) => api.put(`/products/${id}`, data),
};

// Quotations
export const quotationAPI = {
  getAll: (status) => api.get('/quotations', { params: { status } }),
  getOne: (id) => api.get(`/quotations/${id}`),
  create: (data) => api.post('/quotations', data),
  approve: (id) => api.put(`/quotations/${id}/approve`),
  reject: (id) => api.put(`/quotations/${id}/reject`),
};

// Sales Orders
export const salesOrderAPI = {
  getAll: (status) => api.get('/sales-orders', { params: { status } }),
  getOne: (id) => api.get(`/sales-orders/${id}`),
  create: (data) => api.post('/sales-orders', data),
};

// Payments
export const paymentAPI = {
  getAll: (salesOrderId) => api.get('/payments', { params: { sales_order_id: salesOrderId } }),
  create: (data) => api.post('/payments', data),
};

// Job Orders
export const jobOrderAPI = {
  getAll: (status) => api.get('/job-orders', { params: { status } }),
  getOne: (id) => api.get(`/job-orders/${id}`),
  create: (data) => api.post('/job-orders', data),
  updateStatus: (id, status) => api.put(`/job-orders/${id}/status`, null, { params: { status } }),
};

// GRN
export const grnAPI = {
  getAll: () => api.get('/grn'),
  create: (data) => api.post('/grn', data),
};

// Delivery Orders
export const deliveryOrderAPI = {
  getAll: () => api.get('/delivery-orders'),
  create: (data) => api.post('/delivery-orders', data),
};

// Shipping
export const shippingAPI = {
  getAll: (status) => api.get('/shipping-bookings', { params: { status } }),
  create: (data) => api.post('/shipping-bookings', data),
  update: (id, data) => api.put(`/shipping-bookings/${id}`, null, { params: data }),
};

// Transport
export const transportAPI = {
  getAll: (status) => api.get('/transport-schedules', { params: { status } }),
  create: (data) => api.post('/transport-schedules', data),
  update: (id, data) => api.put(`/transport-schedules/${id}`, null, { params: data }),
};

// Documents
export const documentAPI = {
  getAll: (shippingBookingId) => api.get('/export-documents', { params: { shipping_booking_id: shippingBookingId } }),
  create: (data) => api.post('/export-documents', data),
};

// QC
export const qcAPI = {
  getAll: (status) => api.get('/qc-batches', { params: { status } }),
  create: (data) => api.post('/qc-batches', data),
  updateStatus: (id, status) => api.put(`/qc-batches/${id}/status`, null, { params: { status } }),
};

// Inventory
export const inventoryAPI = {
  getAll: (category, lowStock) => api.get('/inventory', { params: { category, low_stock: lowStock } }),
  getMovements: (productId) => api.get('/inventory/movements', { params: { product_id: productId } }),
};

// Dashboard
export const dashboardAPI = {
  getStats: () => api.get('/dashboard/stats'),
  getRecentActivities: () => api.get('/dashboard/recent-activities'),
};

export default api;
