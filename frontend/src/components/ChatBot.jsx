import React, { useState, useEffect, useRef } from 'react';
import { Send, Image as ImageIcon, ShoppingBag, CheckCircle, XCircle, QrCode, Loader, AlertTriangle } from 'lucide-react';
import confetti from 'canvas-confetti';

export default function ChatBot({ session, backendUrl }) {
  const [shops, setShops] = useState([]);
  const [selectedShop, setSelectedShop] = useState(null);
  const [messages, setMessages] = useState([]);
  const [inputText, setInputText] = useState('');
  const [loading, setLoading] = useState(false);
  
  // States for matching draft order review
  const [extractedItems, setExtractedItems] = useState(null);
  const [currentOrder, setCurrentOrder] = useState(null);
  const [showPayment, setShowPayment] = useState(false);
  const [paymentDetails, setPaymentDetails] = useState(null);
  const [ws, setWs] = useState(null);

  const messagesEndRef = useRef(null);
  const fileInputRef = useRef(null);

  // Auto scroll chat
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading, extractedItems]);

  // Connect WebSockets
  useEffect(() => {
    if (session) {
      const socket = new WebSocket(`ws://${backendUrl.replace('http://', '')}/ws/${session.phone_number.replace('+', '')}`);
      
      socket.onopen = () => console.log("WebSocket connected for customer client.");
      
      socket.onmessage = (event) => {
        const data = JSON.parse(event.data);
        console.log("WebSocket message received:", data);
        
        if (data.type === 'order_reviewed' && currentOrder && data.order_id === currentOrder.id) {
          // Fetch updated order details
          fetchOrderDetails(data.order_id);
          addBotMessage(`🔔 Shop Owner reviewed your order #${data.order_id}! Please check the updated items below and confirm payment.`);
        }
        
        if (data.type === 'payment_success' && currentOrder && data.order_id === currentOrder.id) {
          // Trigger confetti!
          confetti({ particleCount: 150, spread: 80, origin: { y: 0.6 } });
          setCurrentOrder(prev => prev ? { ...prev, status: 'paid' } : null);
          setShowPayment(false);
          addBotMessage(`🎉 Payment verified successfully for Order #${data.order_id}! The shop inventory has been automatically updated.`);
        }
      };

      setWs(socket);
      return () => socket.close();
    }
  }, [session, currentOrder]);

  // Fetch shops on mount
  useEffect(() => {
    fetchShops();
  }, []);

  const fetchShops = async () => {
    try {
      const res = await fetch(`${backendUrl}/api/shops/`);
      if (res.ok) {
        const data = await res.json();
        setShops(data);
        if (data.length > 0) {
          addBotMessage("👋 Hello! Please select a shop from the dropdown above to start shopping.");
        } else {
          addBotMessage("👋 Hello! There are no shops registered in the system yet. Please register an owner shop first.");
        }
      }
    } catch (err) {
      console.error(err);
    }
  };

  const fetchOrderDetails = async (orderId) => {
    try {
      const res = await fetch(`${backendUrl}/api/orders/${orderId}`, {
        headers: { 'Authorization': `Bearer ${session.access_token}` }
      });
      if (res.ok) {
        const orderData = await res.json();
        setCurrentOrder(orderData);
      }
    } catch (err) {
      console.error(err);
    }
  };

  const addBotMessage = (text) => {
    setMessages(prev => [...prev, { sender: 'bot', text, time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) }]);
  };

  const addUserMessage = (text) => {
    setMessages(prev => [...prev, { sender: 'user', text, time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) }]);
  };

  const handleShopSelect = (shop) => {
    setSelectedShop(shop);
    addBotMessage(`🏪 You have selected "${shop.name}". You can now type your shopping list below (e.g. "2kg rice, 3 milk, 5 soap") or click the image icon to upload a photo of your shopping list.`);
  };

  const handleSendText = async (e) => {
    e.preventDefault();
    if (!inputText.trim() || !selectedShop) return;

    const text = inputText;
    setInputText('');
    addUserMessage(text);
    setLoading(true);

    try {
      const formData = new FormData();
      formData.append('text', text);

      const res = await fetch(`${backendUrl}/api/orders/process-text?shop_id=${selectedShop.id}`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${session.access_token}` },
        body: formData
      });

      if (res.ok) {
        const data = await res.json();
        setExtractedItems(data.extracted_items);
        addBotMessage("🤖 spaCy NLP completed! Here is the parsed shopping list. Please verify the items and make edits before confirming draft creation.");
      } else {
        addBotMessage("❌ Failed to parse the shopping list. Please try writing in simple terms (e.g. '2kg Rice').");
      }
    } catch (err) {
      console.error(err);
      addBotMessage("❌ Connection error. Failed to reach parsing servers.");
    } finally {
      setLoading(false);
    }
  };

  const handleImageUpload = async (e) => {
    const file = e.target.files[0];
    if (!file || !selectedShop) return;

    addUserMessage(`📷 Uploaded shopping list image: ${file.name}`);
    setLoading(true);

    try {
      const formData = new FormData();
      formData.append('file', file);

      const res = await fetch(`${backendUrl}/api/orders/process-image?shop_id=${selectedShop.id}`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${session.access_token}` },
        body: formData
      });

      if (res.ok) {
        const data = await res.json();
        addBotMessage(`✍️ TrOCR extracted raw text: "${data.raw_text}"`);
        setExtractedItems(data.extracted_items);
        addBotMessage("🤖 Here are the matched products from the shop's catalog. Review, select alternatives for unrecognized items, and submit draft.");
      } else {
        addBotMessage("❌ Failed to run TrOCR image extraction. Please make sure the image is clear.");
      }
    } catch (err) {
      console.error(err);
      addBotMessage("❌ Connection error. Image server could not be reached.");
    } finally {
      setLoading(false);
    }
  };

  // Edit parsed items before creating draft
  const handleItemQtyChange = (index, value) => {
    const updated = [...extractedItems];
    updated[index].quantity = parseFloat(value) || 0;
    setExtractedItems(updated);
  };

  const handleItemSuggestionChange = (index, suggestionId) => {
    const updated = [...extractedItems];
    const item = updated[index];
    const match = item.suggestions.find(s => s.id === parseInt(suggestionId));
    if (match) {
      item.matched_product_id = match.id;
      item.matched_product_name = match.name;
      item.matched_product_price = match.price;
      item.recognized = true;
    }
    setExtractedItems(updated);
  };

  const handleRemoveExtractedItem = (index) => {
    setExtractedItems(prev => prev.filter((_, idx) => idx !== index));
  };

  // Create Draft Order
  const handleCreateDraftOrder = async () => {
    setLoading(true);
    
    // Filter recognized items only
    const validItems = extractedItems.filter(item => item.recognized);
    if (validItems.length === 0) {
      addBotMessage("⚠️ You must have at least one recognized product to submit a draft order.");
      setLoading(false);
      return;
    }

    try {
      const payload = {
        shop_id: selectedShop.id,
        items: validItems.map(i => ({
          product_id: i.matched_product_id,
          quantity: i.quantity,
          unit: i.unit,
          price_at_order: i.matched_product_price
        })),
        notes: "Created via Multimodal Chat Assistant"
      };

      const res = await fetch(`${backendUrl}/api/orders/create-draft`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${session.access_token}`
        },
        body: JSON.stringify(payload)
      });

      if (res.ok) {
        const orderData = await res.json();
        setCurrentOrder(orderData);
        setExtractedItems(null);
        addBotMessage(`📝 Order Draft #${orderData.id} created successfully! Total: ₹${orderData.total_amount}. The shop owner has been notified and is reviewing item availability...`);
      } else {
        addBotMessage("❌ Failed to create the draft order.");
      }
    } catch (err) {
      console.error(err);
      addBotMessage("❌ Network error. Failed to save draft.");
    } finally {
      setLoading(false);
    }
  };

  // Payment integration
  const handleInitiatePayment = async (method) => {
    setLoading(true);
    try {
      const res = await fetch(`${backendUrl}/api/payments/initiate/${currentOrder.id}?method=${method}`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${session.access_token}` }
      });

      if (res.ok) {
        const data = await res.json();
        setPaymentDetails(data);
        setShowPayment(true);
        if (method === 'cash') {
          addBotMessage("💵 Cash payment request recorded. Please pay the owner at the counter.");
        } else {
          addBotMessage("📱 UPI QR Code generated. Please scan the QR code to complete your payment.");
        }
      } else {
        addBotMessage("❌ Payment initiation failed.");
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  // Simulated Webhook triggers
  const handleSimulateWebhook = async () => {
    if (!paymentDetails || !paymentDetails.razorpay_order_id) return;
    
    // Send simulated paid event directly to webhook
    try {
      const res = await fetch(`${backendUrl}/api/payments/webhook`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'x-razorpay-signature': 'sandbox_bypass' },
        body: JSON.stringify({
          event: "order.paid",
          payload: {
            order: { entity: { id: paymentDetails.razorpay_order_id } },
            payment: { entity: { id: "pay_simulated_success_" + Math.random().toString(36).substr(2, 9) } }
          }
        })
      });
      if (res.ok) {
        // WebSocket updates state
      } else {
        alert("Failed to send webhook event");
      }
    } catch (err) {
      console.error(err);
    }
  };

  return (
    <div className="chat-container">
      {/* Top Shop Selector */}
      <div className="chat-header">
        <div>
          <span className="chat-title">💬 Multimodal AI Shopping Chatbot</span>
          {selectedShop && <div style={{ fontSize: '12px', color: 'var(--secondary)' }}>Active: {selectedShop.name}</div>}
        </div>
        <div>
          <select 
            className="suggestions-select" 
            style={{ padding: '6px 12px', fontSize: '13px' }}
            onChange={(e) => {
              const shop = shops.find(s => s.id === parseInt(e.target.value));
              if (shop) handleShopSelect(shop);
            }}
            defaultValue=""
          >
            <option value="" disabled>🏪 Choose a Shop...</option>
            {shops.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
          </select>
        </div>
      </div>

      {/* Message window */}
      <div className="chat-messages">
        {messages.map((m, i) => (
          <div key={i} className={`chat-bubble ${m.sender}`}>
            <div>{m.text}</div>
            <div style={{ fontSize: '9px', textAlign: 'right', marginTop: '4px', opacity: 0.7 }}>{m.time}</div>
          </div>
        ))}

        {/* NLP matching table widget directly in chat */}
        {extractedItems && (
          <div className="order-extraction-card">
            <h4 style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '14px', marginBottom: '10px', color: 'var(--primary)' }}>
              <ShoppingBag size={16} /> Extracted Items Review
            </h4>
            <div style={{ overflowX: 'auto' }}>
              <div className="order-item-row" style={{ fontWeight: '700', fontSize: '11px', textTransform: 'uppercase', color: 'var(--text-secondary)' }}>
                <div>Item</div>
                <div>Qty</div>
                <div>Suggestions / Actions</div>
                <div>Remove</div>
              </div>
              
              {extractedItems.map((item, idx) => (
                <div key={idx} className="order-item-row" style={{ fontSize: '13px' }}>
                  <div>
                    {item.matched_product_name || item.original_name}
                    {!item.recognized && <div className="unrecognized-badge">Unrecognized</div>}
                  </div>
                  <div>
                    <input 
                      type="number" 
                      className="form-input" 
                      style={{ padding: '4px 8px', fontSize: '12px', width: '60px' }}
                      value={item.quantity}
                      onChange={(e) => handleItemQtyChange(idx, e.target.value)}
                    />
                    <span style={{ fontSize: '11px', color: 'var(--text-secondary)', marginLeft: '4px' }}>{item.unit}</span>
                  </div>
                  <div>
                    {!item.recognized && item.suggestions.length > 0 ? (
                      <select 
                        className="suggestions-select"
                        onChange={(e) => handleItemSuggestionChange(idx, e.target.value)}
                        defaultValue=""
                      >
                        <option value="" disabled>Choose replacement...</option>
                        {item.suggestions.map(s => (
                          <option key={s.id} value={s.id}>{s.name} (₹{s.price})</option>
                        ))}
                      </select>
                    ) : (
                      <span style={{ color: 'var(--secondary)', fontSize: '12px' }}>
                        {item.recognized ? `₹${item.matched_product_price} / ${item.unit}` : "No similar items found"}
                      </span>
                    )}
                  </div>
                  <div>
                    <button 
                      className="btn-close-alert" 
                      style={{ color: 'var(--error)' }}
                      onClick={() => handleRemoveExtractedItem(idx)}
                    >
                      Remove
                    </button>
                  </div>
                </div>
              ))}
            </div>

            <div style={{ marginTop: '14px', display: 'flex', gap: '8px' }}>
              <button className="btn-primary" style={{ padding: '8px 16px', fontSize: '13px' }} onClick={handleCreateDraftOrder}>
                Confirm & Send Draft to Owner
              </button>
              <button 
                className="btn-logout" 
                style={{ padding: '8px 16px', fontSize: '13px' }}
                onClick={() => setExtractedItems(null)}
              >
                Cancel
              </button>
            </div>
          </div>
        )}

        {/* Reviewed order state widget */}
        {currentOrder && currentOrder.status === 'pending_customer' && (
          <div className="order-extraction-card" style={{ borderColor: 'var(--secondary)' }}>
            <h4 style={{ color: 'var(--secondary)', fontSize: '14px', marginBottom: '8px' }}>
              🔔 Reviewed Order Draft #{currentOrder.id}
            </h4>
            <p style={{ fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '10px' }}>
              The owner edited quantities or prices according to stock availability. Please accept.
            </p>
            
            <table className="premium-table" style={{ marginTop: '0', marginBottom: '14px' }}>
              <thead>
                <tr>
                  <th>Product</th>
                  <th>Quantity</th>
                  <th>Price</th>
                </tr>
              </thead>
              <tbody>
                {currentOrder.items.map(item => (
                  <tr key={item.id}>
                    <td>{item.product_name}</td>
                    <td>{item.quantity} {item.unit}</td>
                    <td>₹{item.price_at_order * item.quantity}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            
            {currentOrder.notes && <div style={{ fontSize: '12px', padding: '8px', backgroundColor: 'var(--background)', borderRadius: '4px', marginBottom: '12px' }}><strong>Note from Shop:</strong> {currentOrder.notes}</div>}
            
            <div style={{ fontSize: '15px', fontWeight: '800', marginBottom: '14px' }}>Total Amount: ₹{currentOrder.total_amount}</div>
            
            <div style={{ display: 'flex', gap: '8px' }}>
              <button 
                className="btn-primary" 
                style={{ padding: '8px 16px', fontSize: '13px', backgroundColor: 'var(--secondary)' }} 
                onClick={() => handleInitiatePayment('razorpay')}
              >
                Pay Online (Razorpay QR)
              </button>
              <button 
                className="btn-logout" 
                style={{ padding: '8px 16px', fontSize: '13px', borderColor: 'var(--text-secondary)' }}
                onClick={() => handleInitiatePayment('cash')}
              >
                Pay Cash at Shop
              </button>
            </div>
          </div>
        )}

        {/* Razorpay QR display box */}
        {showPayment && paymentDetails && (
          <div className="qr-modal">
            <h4 style={{ fontSize: '14px', marginBottom: '4px' }}>📱 Scan QR to Pay</h4>
            <div style={{ fontSize: '16px', fontWeight: '800', color: 'var(--primary)' }}>₹{paymentDetails.amount}</div>
            
            <img 
              src={`https://api.qrserver.com/v1/create-qr-code/?size=160x160&data=${encodeURIComponent(paymentDetails.upi_uri)}`}
              alt="Razorpay Test QR"
              style={{ margin: '14px 0', border: '1px solid var(--surface-border)', padding: '6px', borderRadius: '4px' }}
            />
            
            <p style={{ fontSize: '11px', color: 'var(--text-secondary)', marginBottom: '14px' }}>
              Razorpay Order ID: <span style={{ fontFamily: 'monospace' }}>{paymentDetails.razorpay_order_id}</span>
            </p>

            <button 
              className="btn-primary" 
              style={{ width: '100%', fontSize: '13px' }}
              onClick={handleSimulateWebhook}
            >
              Simulate Webhook Success (Demo)
            </button>
          </div>
        )}

        {loading && (
          <div style={{ alignSelf: 'flex-start', display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--text-secondary)' }}>
            <Loader size={18} className="animate-spin" /> <span style={{ fontSize: '13px' }}>AI is thinking...</span>
          </div>
        )}
        
        <div ref={messagesEndRef} />
      </div>

      {/* Input area */}
      <div className="chat-input-area">
        <button 
          className="btn-icon"
          onClick={() => fileInputRef.current?.click()}
          title="Upload image shopping list (TrOCR)"
          disabled={!selectedShop}
        >
          <ImageIcon size={20} />
        </button>
        <input 
          type="file" 
          ref={fileInputRef} 
          style={{ display: 'none' }} 
          accept="image/*"
          onChange={handleImageUpload}
        />
        
        <form onSubmit={handleSendText} style={{ display: 'flex', flex: 1, gap: '8px' }}>
          <input 
            type="text"
            className="chat-text-area"
            placeholder={selectedShop ? "Type items list here..." : "Please select a shop first"}
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            disabled={!selectedShop}
          />
          <button 
            type="submit" 
            className="btn-icon send"
            disabled={!selectedShop || !inputText.trim()}
          >
            <Send size={18} />
          </button>
        </form>
      </div>
    </div>
  );
}
