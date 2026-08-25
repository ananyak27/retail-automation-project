import React, { useState, useEffect } from 'react';
import { 
  Plus, Play, AlertOctagon, TrendingUp, Check, Bell, Save, Trash, RefreshCw, Layers
} from 'lucide-react';
import { Line } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler
} from 'chart.js';

// Register ChartJS elements
ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler
);

export default function OwnerDashboard({ session, backendUrl }) {
  const [shop, setShop] = useState(null);
  const [ownerProfile, setOwnerProfile] = useState(null);
  const [newShopName, setNewShopName] = useState('');
  const [products, setProducts] = useState([]);
  const [orders, setOrders] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [activeTab, setActiveTab] = useState('orders'); // 'orders', 'inventory', 'alerts', 'forecast', 'profile'
  
  // Create product form state
  const [newProdName, setNewProdName] = useState('');
  const [newProdUnit, setNewProdUnit] = useState('kg');
  const [newProdPrice, setNewProdPrice] = useState('');
  const [newProdStock, setNewProdStock] = useState('');
  const [newProdThreshold, setNewProdThreshold] = useState('10');
  
  // Selected order for review
  const [reviewOrder, setReviewOrder] = useState(null);
  const [reviewItems, setReviewItems] = useState([]);
  const [reviewNotes, setReviewNotes] = useState('');

  // Selected product for Prophet forecasting
  const [selectedForecastProduct, setSelectedForecastProduct] = useState('');
  const [forecastPeriod, setForecastPeriod] = useState(7);
  const [forecastData, setForecastData] = useState(null);
  const [loading, setLoading] = useState(false);

  // Fetch shop and profile details on load
  useEffect(() => {
    fetchMyShop();
    fetchOwnerProfile();
  }, []);

  // Poll for database details when shop is loaded
  useEffect(() => {
    if (shop) {
      fetchProducts();
      fetchOrders();
      fetchAlerts();

      // Setup WebSocket for real-time dashboard alerts
      const socket = new WebSocket(`ws://${backendUrl.replace('http://', '')}/ws/${session.phone_number.replace('+', '')}`);
      
      socket.onmessage = (event) => {
        const data = JSON.parse(event.data);
        console.log("WebSocket Owner received alert:", data);
        
        // Refresh alert list and orders list automatically
        fetchAlerts();
        fetchOrders();
        fetchProducts(); // Refresh stock levels
      };

      return () => socket.close();
    }
  }, [shop]);

  const fetchMyShop = async () => {
    try {
      const res = await fetch(`${backendUrl}/api/shops/my-shop`, {
        headers: { 'Authorization': `Bearer ${session.access_token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setShop(data);
      }
    } catch (err) {
      console.log("No shop registered yet.");
    }
  };

  const fetchOwnerProfile = async () => {
    try {
      const res = await fetch(`${backendUrl}/api/auth/me`, {
        headers: { 'Authorization': `Bearer ${session.access_token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setOwnerProfile(data);
      }
    } catch (err) {
      console.error("Could not fetch owner profile.", err);
    }
  };

  const handleRegisterShop = async (e) => {
    e.preventDefault();
    if (!newShopName.trim()) return;

    try {
      const res = await fetch(`${backendUrl}/api/shops/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${session.access_token}`
        },
        body: JSON.stringify({ name: newShopName })
      });
      if (res.ok) {
        const data = await res.json();
        setShop(data);
      } else {
        alert("Shop registration failed.");
      }
    } catch (err) {
      console.error(err);
    }
  };

  const fetchProducts = async () => {
    if (!shop) return;
    try {
      const res = await fetch(`${backendUrl}/api/products/?shop_id=${shop.id}`);
      if (res.ok) {
        const data = await res.json();
        setProducts(data);
        if (data.length > 0 && !selectedForecastProduct) {
          setSelectedForecastProduct(data[0].id.toString());
          fetchForecast(data[0].id);
        }
      }
    } catch (err) {
      console.error(err);
    }
  };

  const fetchOrders = async () => {
    if (!shop) return;
    try {
      const res = await fetch(`${backendUrl}/api/orders/?shop_id=${shop.id}`, {
        headers: { 'Authorization': `Bearer ${session.access_token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setOrders(data);
      }
    } catch (err) {
      console.error(err);
    }
  };

  const fetchAlerts = async () => {
    if (!shop) return;
    try {
      const res = await fetch(`${backendUrl}/api/alerts/?shop_id=${shop.id}`, {
        headers: { 'Authorization': `Bearer ${session.access_token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setAlerts(data.filter(a => !a.is_read));
      }
    } catch (err) {
      console.error(err);
    }
  };

  const handleAddProduct = async (e) => {
    e.preventDefault();
    if (!newProdName.trim() || !newProdPrice || !newProdStock) return;

    try {
      const res = await fetch(`${backendUrl}/api/products/?shop_id=${shop.id}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${session.access_token}`
        },
        body: JSON.stringify({
          name: newProdName,
          unit: newProdUnit,
          price: parseFloat(newProdPrice),
          stock: parseFloat(newProdStock),
          min_stock_threshold: parseFloat(newProdThreshold)
        })
      });

      if (res.ok) {
        // Clear fields
        setNewProdName('');
        setNewProdPrice('');
        setNewProdStock('');
        setNewProdThreshold('10');
        fetchProducts();
        alert("Product added successfully! Initial 90 days sales seed data generated for forecasting models.");
      } else {
        alert("Failed to add product");
      }
    } catch (err) {
      console.error(err);
    }
  };

  const handleMarkAlertRead = async (alertId) => {
    try {
      const res = await fetch(`${backendUrl}/api/alerts/${alertId}/read`, {
        method: 'PUT',
        headers: { 'Authorization': `Bearer ${session.access_token}` }
      });
      if (res.ok) {
        fetchAlerts();
      }
    } catch (err) {
      console.error(err);
    }
  };

  // Select order to review
  const initiateOrderReview = (order) => {
    setReviewOrder(order);
    setReviewItems(order.items.map(i => ({ ...i })));
    setReviewNotes(order.notes || '');
  };

  const handleReviewQtyChange = (index, value) => {
    const updated = [...reviewItems];
    updated[index].quantity = parseFloat(value) || 0;
    setReviewItems(updated);
  };

  const handleReviewPriceChange = (index, value) => {
    const updated = [...reviewItems];
    updated[index].price_at_order = parseFloat(value) || 0;
    setReviewItems(updated);
  };

  const handleRemoveReviewItem = (index) => {
    setReviewItems(prev => prev.filter((_, idx) => idx !== index));
  };

  const handleSubmitReview = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${backendUrl}/api/orders/${reviewOrder.id}/review`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${session.access_token}`
        },
        body: JSON.stringify({
          items: reviewItems.map(i => ({
            product_id: i.product_id,
            quantity: i.quantity,
            unit: i.unit,
            price_at_order: i.price_at_order
          })),
          notes: reviewNotes
        })
      });

      if (res.ok) {
        setReviewOrder(null);
        fetchOrders();
        alert("Reviewed order sent back to customer successfully!");
      } else {
        alert("Failed to save order review.");
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleConfirmCashPayment = async (orderId) => {
    if (!confirm("Confirm cash payment received? This will deduct catalog inventory.")) return;
    try {
      const res = await fetch(`${backendUrl}/api/payments/confirm-cash/${orderId}`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${session.access_token}` }
      });
      if (res.ok) {
        fetchOrders();
        fetchProducts(); // Refresh stock levels
        alert("Cash payment confirmed. Stock quantities deducted.");
      } else {
        alert("Failed to confirm cash payment.");
      }
    } catch (err) {
      console.error(err);
    }
  };

  /// Fetch Prophet Forecast data
  const fetchForecast = async (productId, period = forecastPeriod) => {
    try {
      const res = await fetch(`${backendUrl}/api/forecasts/product/${productId}?periods=${period}`, {
        headers: { 'Authorization': `Bearer ${session.access_token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setForecastData(data);
      }
    } catch (err) {
      console.error(err);
    }
  };

  const handleForecastProductChange = (productId) => {
    setSelectedForecastProduct(productId);
    fetchForecast(productId, forecastPeriod);
  };

  // Calculations for stats
  const totalSales = orders
    .filter(o => o.status === 'paid')
    .reduce((sum, o) => sum + o.total_amount, 0);

  const activeOrdersCount = orders
    .filter(o => o.status === 'pending_owner' || o.status === 'pending_customer' || o.status === 'pending_payment')
    .length;

  const lowStockCount = products.filter(p => p.stock <= p.min_stock_threshold).length;

  // Chart configuration
  const getChartConfig = () => {
    if (!forecastData || forecastData.forecast.length === 0) return null;

    const labels = forecastData.forecast.map(f => f.ds);
    const predictions = forecastData.forecast.map(f => f.yhat);
    const lowerBounds = forecastData.forecast.map(f => f.yhat_lower);
    const upperBounds = forecastData.forecast.map(f => f.yhat_upper);

    return {
      labels,
      datasets: [
        {
          label: 'Predicted Sales Demand',
          data: predictions,
          borderColor: 'rgb(59, 130, 246)',
          backgroundColor: 'rgba(59, 130, 246, 0.1)',
          tension: 0.3,
          fill: true,
          pointRadius: 4,
          pointBackgroundColor: 'rgb(59, 130, 246)'
        },
        {
          label: 'Upper Limit Demand',
          data: upperBounds,
          borderColor: 'rgba(16, 185, 129, 0.4)',
          borderDash: [5, 5],
          pointRadius: 0,
          fill: false
        },
        {
          label: 'Lower Limit Demand',
          data: lowerBounds,
          borderColor: 'rgba(239, 68, 68, 0.4)',
          borderDash: [5, 5],
          pointRadius: 0,
          fill: false
        }
      ]
    };
  };

  // If no shop, register first
  if (!shop) {
    return (
      <div className="auth-page">
        <div className="auth-card" style={{ maxWidth: '480px' }}>
          <div style={{ display: 'flex', justifyContent: 'center', marginBottom: '16px', color: 'var(--primary)' }}>
            <Layers size={48} />
          </div>
          <h2 className="auth-title">Register Your Shop</h2>
          <p className="auth-subtitle">Get started by creating your retail shop catalog</p>
          
          <form onSubmit={handleRegisterShop}>
            <div className="form-group">
              <label className="form-label">Shop Name</label>
              <input 
                type="text" 
                className="form-input" 
                placeholder="Fresh Mart / City Superstore"
                value={newShopName}
                onChange={(e) => setNewShopName(e.target.value)}
                required
              />
            </div>
            <button type="submit" className="btn-primary">
              Create Shop & Initialize
            </button>
          </form>
        </div>
      </div>
    );
  }

  return (
    <div className="dashboard-grid">
      {/* Sidebar Navigation */}
      <div className="sidebar">
        <div style={{ paddingBottom: '16px', borderBottom: '1px solid var(--surface-border)', marginBottom: '10px' }}>
          <h3 style={{ fontSize: '18px' }}>🏪 {shop.name}</h3>
          <span style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>Shop ID: {shop.id}</span>
        </div>
        
        <button 
          className={`sidebar-btn ${activeTab === 'orders' ? 'active' : ''}`}
          onClick={() => { setActiveTab('orders'); setReviewOrder(null); }}
        >
          📦 Orders & Processing
        </button>
        <button 
          className={`sidebar-btn ${activeTab === 'inventory' ? 'active' : ''}`}
          onClick={() => setActiveTab('inventory')}
        >
          🥦 Inventory Setup
        </button>
        <button 
          className={`sidebar-btn ${activeTab === 'forecast' ? 'active' : ''}`}
          onClick={() => setActiveTab('forecast')}
        >
          📈 Predictive Demand
        </button>
        <button 
          className={`sidebar-btn ${activeTab === 'profile' ? 'active' : ''}`}
          onClick={() => setActiveTab('profile')}
        >
          👤 Owner Profile
        </button>
        
        {alerts.length > 0 && (
          <div style={{ marginTop: 'auto', backgroundColor: 'var(--error-light)', padding: '12px', borderRadius: 'var(--radius-sm)', borderLeft: '4px solid var(--error)', fontSize: '12px', color: 'var(--error)' }}>
            <strong>{alerts.length} Warnings pending!</strong>
          </div>
        )}
      </div>

      {/* Main Panel */}
      <div>
        {/* Alerts Banner */}
        {alerts.map(a => (
          <div key={a.id} className={`alert-banner ${a.type}`}>
            <span className="alert-message">
              ⚠️ {a.message}
            </span>
            <button className="btn-close-alert" onClick={() => handleMarkAlertRead(a.id)}>
              Dismiss
            </button>
          </div>
        ))}

        {/* Statistics Widgets Row */}
        <div className="stats-row">
          <div className="stat-card">
            <span className="stat-title">Total Sales Revenue</span>
            <span className="stat-value">₹{totalSales.toFixed(2)}</span>
            <span className="stat-desc">Deducted from catalog purchases</span>
          </div>
          <div className="stat-card">
            <span className="stat-title">Active Orders</span>
            <span className="stat-value">{activeOrdersCount}</span>
            <span className="stat-desc">Awaiting review or payment</span>
          </div>
          <div className="stat-card" style={{ borderLeft: lowStockCount > 0 ? '4px solid var(--error)' : '1px solid var(--surface-border)' }}>
            <span className="stat-title">Low Stock Items</span>
            <span className="stat-value" style={{ color: lowStockCount > 0 ? 'var(--error)' : 'inherit' }}>{lowStockCount}</span>
            <span className="stat-desc">Below min threshold</span>
          </div>
        </div>

        {/* Tab content 1: Orders and Cash confirmation */}
        {activeTab === 'orders' && !reviewOrder && (
          <div className="card-content">
            <h3 style={{ fontSize: '18px', display: 'flex', alignItems: 'center', gap: '8px' }}>
              📦 Orders Waiting Action
            </h3>
            
            {orders.length === 0 ? (
              <p style={{ color: 'var(--text-secondary)', fontSize: '14px', textAlign: 'center', padding: '40px' }}>No orders placed yet.</p>
            ) : (
              <div style={{ overflowX: 'auto' }}>
                <table className="premium-table">
                  <thead>
                    <tr>
                      <th>Order ID</th>
                      <th>Customer Phone</th>
                      <th>Total Amount</th>
                      <th>Status</th>
                      <th>Payment</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {orders.map(o => (
                      <tr key={o.id}>
                        <td>#{o.id}</td>
                        <td>{o.customer_id}</td>
                        <td>₹{o.total_amount}</td>
                        <td>
                          <span className={`badge-status ${o.status}`}>{o.status}</span>
                        </td>
                        <td>
                          {o.payment_method ? (
                            <span style={{ fontSize: '12px', fontWeight: '600', textTransform: 'capitalize' }}>
                              {o.payment_method}
                            </span>
                          ) : (
                            <span style={{ color: 'var(--text-muted)', fontSize: '12px' }}>Unselected</span>
                          )}
                        </td>
                        <td>
                          <div style={{ display: 'flex', gap: '8px' }}>
                            {o.status === 'pending_owner' && (
                              <button 
                                className="btn-primary" 
                                style={{ padding: '6px 12px', fontSize: '12px' }}
                                onClick={() => initiateOrderReview(o)}
                              >
                                Review & Edit
                              </button>
                            )}
                            {o.status === 'pending_payment' && o.payment_method === 'cash' && (
                              <button 
                                className="btn-primary" 
                                style={{ padding: '6px 12px', fontSize: '12px', backgroundColor: 'var(--secondary)' }}
                                onClick={() => handleConfirmCashPayment(o.id)}
                              >
                                Confirm Cash Paid
                              </button>
                            )}
                            <button 
                              className="btn-logout"
                              style={{ padding: '6px 12px', fontSize: '12px' }}
                              onClick={() => {
                                alert(`Order Items: \n` + o.items.map(i => `- ${i.product_name}: ${i.quantity} ${i.unit} (₹${i.price_at_order})`).join('\n'));
                              }}
                            >
                              View Items
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {/* Order review page overlay */}
        {activeTab === 'orders' && reviewOrder && (
          <div className="card-content">
            <h3 style={{ fontSize: '18px' }}>✍️ Review Order Draft #{reviewOrder.id}</h3>
            <p style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>
              Check availability. You can modify quantities, remove items, adjust prices, and add notes before sending to customer.
            </p>
            
            <div style={{ overflowX: 'auto' }}>
              <table className="premium-table">
                <thead>
                  <tr>
                    <th>Product</th>
                    <th>Quantity</th>
                    <th>Price / Unit</th>
                    <th>Total</th>
                    <th>Remove</th>
                  </tr>
                </thead>
                <tbody>
                  {reviewItems.map((item, idx) => (
                    <tr key={idx}>
                      <td>{item.product_name}</td>
                      <td>
                        <input 
                          type="number" 
                          className="form-input" 
                          style={{ padding: '6px 10px', fontSize: '13px', width: '80px' }}
                          value={item.quantity}
                          onChange={(e) => handleReviewQtyChange(idx, e.target.value)}
                        />
                        <span style={{ fontSize: '12px', color: 'var(--text-secondary)', marginLeft: '6px' }}>{item.unit}</span>
                      </td>
                      <td>
                        <input 
                          type="number" 
                          className="form-input" 
                          style={{ padding: '6px 10px', fontSize: '13px', width: '100px' }}
                          value={item.price_at_order}
                          onChange={(e) => handleReviewPriceChange(idx, e.target.value)}
                        />
                      </td>
                      <td>₹{(item.quantity * item.price_at_order).toFixed(2)}</td>
                      <td>
                        <button className="btn-close-alert" style={{ color: 'var(--error)' }} onClick={() => handleRemoveReviewItem(idx)}>
                          Remove
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="form-group" style={{ marginTop: '10px' }}>
              <label className="form-label">Reviewer Notes (e.g. "Deducted rice quantity due to limited availability")</label>
              <textarea 
                className="form-input" 
                rows="2"
                style={{ resize: 'none' }}
                value={reviewNotes}
                onChange={(e) => setReviewNotes(e.target.value)}
              />
            </div>

            <div style={{ display: 'flex', gap: '10px', marginTop: '10px' }}>
              <button className="btn-primary" onClick={handleSubmitReview} disabled={loading}>
                {loading ? "Saving..." : "Send Updated Order to Customer"}
              </button>
              <button className="btn-logout" onClick={() => setReviewOrder(null)}>
                Cancel
              </button>
            </div>
          </div>
        )}

        {/* Tab content 2: Inventory setup */}
        {activeTab === 'inventory' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
            <div className="card-content">
              <h3 style={{ fontSize: '18px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Plus size={18} /> Add New Catalog Product
              </h3>
              <form onSubmit={handleAddProduct} style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '16px', alignItems: 'end' }}>
                <div className="form-group" style={{ marginBottom: 0 }}>
                  <label className="form-label">Product Name</label>
                  <input type="text" className="form-input" placeholder="Rice / Milk" value={newProdName} onChange={e => setNewProdName(e.target.value)} required />
                </div>
                <div className="form-group" style={{ marginBottom: 0 }}>
                  <label className="form-label">Unit</label>
                  <select className="form-input" value={newProdUnit} onChange={e => setNewProdUnit(e.target.value)}>
                    <option value="kg">kg</option>
                    <option value="litre">litre</option>
                    <option value="piece">piece</option>
                    <option value="packet">packet</option>
                  </select>
                </div>
                <div className="form-group" style={{ marginBottom: 0 }}>
                  <label className="form-label">Price (₹)</label>
                  <input type="number" className="form-input" placeholder="65" value={newProdPrice} onChange={e => setNewProdPrice(e.target.value)} required />
                </div>
                <div className="form-group" style={{ marginBottom: 0 }}>
                  <label className="form-label">Initial Stock</label>
                  <input type="number" className="form-input" placeholder="100" value={newProdStock} onChange={e => setNewProdStock(e.target.value)} required />
                </div>
                <div className="form-group" style={{ marginBottom: 0 }}>
                  <label className="form-label">Min Threshold</label>
                  <input type="number" className="form-input" placeholder="10" value={newProdThreshold} onChange={e => setNewProdThreshold(e.target.value)} />
                </div>
                <button type="submit" className="btn-primary" style={{ height: '46px' }}>Add Product</button>
              </form>
            </div>

            <div className="card-content">
              <h3 style={{ fontSize: '18px' }}>🥦 Shop Inventory Catalog</h3>
              <div style={{ overflowX: 'auto' }}>
                <table className="premium-table">
                  <thead>
                    <tr>
                      <th>Product</th>
                      <th>Price</th>
                      <th>Stock Level</th>
                      <th>Min Threshold</th>
                      <th>Unit</th>
                    </tr>
                  </thead>
                  <tbody>
                    {products.map(p => (
                      <tr key={p.id} style={{ backgroundColor: p.stock <= p.min_stock_threshold ? 'var(--error-light)' : 'inherit' }}>
                        <td style={{ fontWeight: '700' }}>{p.name}</td>
                        <td>₹{p.price}</td>
                        <td>
                          <span style={{ color: p.stock <= p.min_stock_threshold ? 'var(--error)' : 'inherit', fontWeight: '700' }}>
                            {p.stock}
                          </span>
                        </td>
                        <td>{p.min_stock_threshold}</td>
                        <td style={{ textTransform: 'lowercase' }}>{p.unit}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* Tab content 3: Forecasting dashboard */}
        {activeTab === 'forecast' && (
          <div className="card-content">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h3 style={{ fontSize: '18px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                📈 Meta Prophet Demand Forecasting
              </h3>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <span style={{ fontSize: '13px', fontWeight: '600', color: 'var(--text-secondary)' }}>Select Product:</span>
                <select 
                  className="suggestions-select" 
                  value={selectedForecastProduct}
                  onChange={(e) => handleForecastProductChange(e.target.value)}
                  style={{ padding: '6px 12px' }}
                >
                  {products.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
                </select>
                <select
                  className="suggestions-select"
                  value={forecastPeriod}
                  onChange={(e) => {
                    const period = parseInt(e.target.value, 10);
                    setForecastPeriod(period);

                    if (selectedForecastProduct) {
                      fetchForecast(selectedForecastProduct, period);
                    }
                  }}
                  style={{ padding: '6px 12px' }}
                >
                  <option value={7}>Next 7 Days</option>
                  <option value={14}>Next 14 Days</option>
                  <option value={30}>Next 1 Month</option>
                </select>
              </div>
            </div>

            <p style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>
              Using the trained Meta Prophet model, this dashboard predicts future product demand for the selected forecasting period.
            </p>

            {forecastData && forecastData.forecast.length > 0 ? (
              <div>
                <div className="forecast-chart-container">
                  <Line 
                    data={getChartConfig()} 
                    options={{
                      responsive: true,
                      maintainAspectRatio: false,
                      plugins: {
                        legend: { position: 'top' },
                        tooltip: { mode: 'index', intersect: false }
                      },
                      scales: {
                        y: { title: { display: true, text: 'Quantity demanded' } },
                        x: { title: { display: true, text: 'Future Timeline (Days)' } }
                      }
                    }}
                  />
                </div>
                
                <h4 style={{ fontSize: '14px', marginTop: '24px', marginBottom: '10px' }}>📋 Predicted Stock Recommendation Summary</h4>
                <div style={{ overflowX: 'auto' }}>
                  <table className="premium-table">
                    <thead>
                      <tr>
                        <th>Date</th>
                        <th>Recommended Stock</th>
                        <th>Confidence Bounds (Lower - Upper)</th>
                      </tr>
                    </thead>
                    <tbody>
                      {forecastData.forecast.map((f, idx) => {
                        const selectedProduct = products.find(
                          p => Number(p.id) === Number(selectedForecastProduct)
                        );

                        const unit = selectedProduct?.unit || 'units';

                        const formatForecastValue = (value, unit) => {
                          if (['piece', 'bottle', 'pack'].includes(unit)) {
                            return Math.round(value);
                          }

                          if (unit === 'litre') {
                            return Math.round(value * 2) / 2;
                          }

                          return Number(value).toFixed(2);
                        };

                        const predictedValue = formatForecastValue(f.yhat, unit);
                        const lowerValue = formatForecastValue(f.yhat_lower, unit);
                        const upperValue = formatForecastValue(f.yhat_upper, unit);

                        return (
                          <tr key={idx}>
                            <td>{f.ds}</td>
                            <td style={{ fontWeight: '700', color: 'var(--primary)' }}>
                              {predictedValue} {unit}
                            </td>
                            <td>
                              {lowerValue} to {upperValue} {unit}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            ) : (
              <p style={{ color: 'var(--text-secondary)', textAlign: 'center', padding: '40px' }}>
                Gathering history records... (Wait a moment or ensure products are added)
              </p>
            )}
          </div>
        )}

        {/* Tab content 4: Owner Profile */}
        {activeTab === 'profile' && (
          <div className="card-content">
            <h3 style={{ fontSize: '18px', marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
              👤 Shop Owner Profile & Business Details
            </h3>
            <p style={{ fontSize: '13px', color: 'var(--text-secondary)', marginBottom: '24px' }}>
              Stored personal, business, and bank payment information registered with your retail account.
            </p>

            {/* Personal Information */}
            <div style={{ marginBottom: '24px', backgroundColor: 'var(--surface-light)', padding: '20px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--surface-border)' }}>
              <h4 style={{ fontSize: '14px', color: 'var(--primary)', marginBottom: '14px', fontWeight: '600', letterSpacing: '0.5px' }}>
                PERSONAL INFORMATION
              </h4>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', fontSize: '14px' }}>
                <div>
                  <span style={{ color: 'var(--text-secondary)', fontSize: '12px', display: 'block', marginBottom: '4px' }}>Owner Name</span>
                  <strong>{ownerProfile?.owner_name || 'N/A'}</strong>
                </div>
                <div>
                  <span style={{ color: 'var(--text-secondary)', fontSize: '12px', display: 'block', marginBottom: '4px' }}>Mobile Number</span>
                  <strong>{ownerProfile?.phone_number || session.phone_number}</strong>
                </div>
              </div>
            </div>

            {/* Business Information */}
            <div style={{ marginBottom: '24px', backgroundColor: 'var(--surface-light)', padding: '20px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--surface-border)' }}>
              <h4 style={{ fontSize: '14px', color: 'var(--primary)', marginBottom: '14px', fontWeight: '600', letterSpacing: '0.5px' }}>
                BUSINESS INFORMATION
              </h4>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', fontSize: '14px' }}>
                <div>
                  <span style={{ color: 'var(--text-secondary)', fontSize: '12px', display: 'block', marginBottom: '4px' }}>Shop Name</span>
                  <strong>{shop?.name || 'N/A'}</strong>
                </div>
                <div>
                  <span style={{ color: 'var(--text-secondary)', fontSize: '12px', display: 'block', marginBottom: '4px' }}>Shop Address</span>
                  <strong>{shop?.address || 'N/A'}</strong>
                </div>
              </div>
            </div>

            {/* Payment Information */}
            <div style={{ backgroundColor: 'var(--surface-light)', padding: '20px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--surface-border)' }}>
              <h4 style={{ fontSize: '14px', color: 'var(--primary)', marginBottom: '14px', fontWeight: '600', letterSpacing: '0.5px' }}>
                PAYMENT INFORMATION
              </h4>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', marginBottom: '16px', fontSize: '14px' }}>
                <div>
                  <span style={{ color: 'var(--text-secondary)', fontSize: '12px', display: 'block', marginBottom: '4px' }}>Bank Account Holder Name</span>
                  <strong>{ownerProfile?.bank_account_holder_name || 'N/A'}</strong>
                </div>
                <div>
                  <span style={{ color: 'var(--text-secondary)', fontSize: '12px', display: 'block', marginBottom: '4px' }}>Bank Name</span>
                  <strong>{ownerProfile?.bank_name || 'N/A'}</strong>
                </div>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '16px', fontSize: '14px' }}>
                <div>
                  <span style={{ color: 'var(--text-secondary)', fontSize: '12px', display: 'block', marginBottom: '4px' }}>Masked Account Number</span>
                  <strong>
                    {ownerProfile?.account_number
                      ? ownerProfile.account_number.length > 4
                        ? '******' + ownerProfile.account_number.slice(-4)
                        : ownerProfile.account_number
                      : 'N/A'}
                  </strong>
                </div>
                <div>
                  <span style={{ color: 'var(--text-secondary)', fontSize: '12px', display: 'block', marginBottom: '4px' }}>IFSC Code</span>
                  <strong>{ownerProfile?.ifsc_code || 'N/A'}</strong>
                </div>
                <div>
                  <span style={{ color: 'var(--text-secondary)', fontSize: '12px', display: 'block', marginBottom: '4px' }}>UPI ID</span>
                  <strong>{ownerProfile?.upi_id || 'N/A'}</strong>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
