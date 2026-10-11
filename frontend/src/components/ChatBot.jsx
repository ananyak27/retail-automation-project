import React, { useState, useEffect, useRef } from 'react';
import { Send, Image as ImageIcon, ShoppingBag, Trash2, Store, Loader } from 'lucide-react';
import confetti from 'canvas-confetti';
import { getWebSocketUrl } from '../App';
import { formatDateTime } from '../utils/dateTimeUtils';

export default function ChatBot({ session, backendUrl }) {
  const [shops, setShops] = useState([]);
  const [selectedShop, setSelectedShop] = useState(null);
  const [shopCatalog, setShopCatalog] = useState([]);
  const [catalogSearchQuery, setCatalogSearchQuery] = useState('');
  const [customerOrders, setCustomerOrders] = useState([]);
  const [messages, setMessages] = useState([]);

  const [inputText, setInputText] = useState('');
  const [loading, setLoading] = useState(false);

  // States for draft order review & payment
  const [extractedItems, setExtractedItems] = useState(null);
  const [currentOrder, setCurrentOrder] = useState(null);
  const [showPayment, setShowPayment] = useState(false);
  const [paymentDetails, setPaymentDetails] = useState(null);
  const [activePaymentOrderId, setActivePaymentOrderId] = useState(null);
  const [isConnected, setIsConnected] = useState(false);

  const messagesEndRef = useRef(null);
  const fileInputRef = useRef(null);

  const socketRef = useRef(null);
  const reconnectTimerRef = useRef(null);
  const isMountedRef = useRef(true);
  const selectedShopRef = useRef(selectedShop);
  const currentOrderRef = useRef(currentOrder);

  useEffect(() => {
    selectedShopRef.current = selectedShop;
  }, [selectedShop]);

  useEffect(() => {
    currentOrderRef.current = currentOrder;
  }, [currentOrder]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, extractedItems, currentOrder, loading]);

  const fetchCustomerOrders = async () => {
    if (!session?.access_token) return;
    try {
      const res = await fetch(`${backendUrl}/api/orders/`, {
        headers: { 'Authorization': `Bearer ${session.access_token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setCustomerOrders(data);
        if (currentOrderRef.current) {
          const updated = data.find(o => o.id === currentOrderRef.current.id);
          if (updated) {
            setCurrentOrder(updated);
          }
        }
      }
    } catch (err) {
      console.error("Error fetching customer orders:", err);
    }
  };

  // Robust Customer WebSocket with auto-reconnect & single-socket enforcement
  useEffect(() => {
    isMountedRef.current = true;

    const connectWebSocket = () => {
      if (!session || !session.access_token) return;

      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }

      if (socketRef.current) {
        socketRef.current.onopen = null;
        socketRef.current.onmessage = null;
        socketRef.current.onerror = null;
        socketRef.current.onclose = null;
        try {
          socketRef.current.close();
        } catch (e) {}
        socketRef.current = null;
      }

      const wsUrl = getWebSocketUrl(backendUrl, session.access_token);
      console.log(`[ChatBot] Connecting WebSocket to: ${wsUrl}`);
      const socket = new WebSocket(wsUrl);
      socketRef.current = socket;

      socket.onopen = () => {
        if (!isMountedRef.current) return;
        console.log("[ChatBot] WebSocket connected successfully.");
        setIsConnected(true);
      };

      socket.onmessage = (event) => {
        if (!isMountedRef.current) return;
        try {
          const data = JSON.parse(event.data);
          console.log("[ChatBot] WebSocket message received:", data);

          if (data.type === 'chat_message' && data.data) {
            if (data.data.shop_id === selectedShopRef.current?.id) {
              setMessages(prev => {
                if (prev.some(m => m.id === data.data.id)) return prev;
                return [...prev, data.data];
              });
            }
          }

          if (data.type === 'order_reviewed' || data.type === 'order_rejected' || data.type === 'order_deleted') {
            fetchCustomerOrders();
          }

          if (data.type === 'payment_success') {
            confetti({ particleCount: 150, spread: 80, origin: { y: 0.6 } });
            setShowPayment(false);
            setActivePaymentOrderId(null);
            fetchCustomerOrders();
          }
        } catch (err) {
          console.error("[ChatBot] Error parsing WebSocket message:", err);
        }
      };

      socket.onerror = (error) => {
        console.warn("[ChatBot] WebSocket error:", error);
        if (isMountedRef.current) {
          setIsConnected(false);
        }
      };

      socket.onclose = (event) => {
        console.log(`[ChatBot] WebSocket disconnected (code: ${event.code}).`);
        if (isMountedRef.current) {
          setIsConnected(false);
          if (!reconnectTimerRef.current) {
            reconnectTimerRef.current = setTimeout(() => {
              reconnectTimerRef.current = null;
              if (isMountedRef.current) {
                console.log("[ChatBot] Auto-reconnecting WebSocket...");
                connectWebSocket();
              }
            }, 3000);
          }
        }
      };
    };

    connectWebSocket();

    return () => {
      isMountedRef.current = false;
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
      if (socketRef.current) {
        socketRef.current.onopen = null;
        socketRef.current.onmessage = null;
        socketRef.current.onerror = null;
        socketRef.current.onclose = null;
        try {
          socketRef.current.close();
        } catch (e) {}
        socketRef.current = null;
      }
    };
  }, [session?.user_id, backendUrl]);

  // Fetch shops and order history on mount
  useEffect(() => {
    fetchShops();
    fetchCustomerOrders();
  }, []);

  const saveChatMessage = async (shopId, senderRole, text) => {
    if (!session?.access_token || !shopId) return null;
    try {
      await fetch(`${backendUrl}/api/chat/messages`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${session.access_token}`
        },
        body: JSON.stringify({
          shop_id: shopId,
          sender_role: senderRole,
          message: text
        })
      });
    } catch (err) {
      console.error("Error saving chat message:", err);
    }
  };

  const fetchShops = async () => {
    try {
      const res = await fetch(`${backendUrl}/api/shops/`);
      if (res.ok) {
        const data = await res.json();
        setShops(data);

        // Auto-restore selected shop from localStorage after refresh
        const savedShopId = localStorage.getItem('customer_selected_shop_id');
        if (savedShopId && data.length > 0) {
          const matched = data.find(s => s.id === parseInt(savedShopId));
          if (matched) {
            handleShopSelect(matched);
          }
        }
      }
    } catch (err) {
      console.error(err);
    }
  };

  const fetchShopCatalog = async (shopId) => {
    try {
      const res = await fetch(`${backendUrl}/api/products/?shop_id=${shopId}`);
      if (res.ok) {
        const data = await res.json();
        setShopCatalog(data);
      }
    } catch (err) {
      console.error("Error fetching shop catalog:", err);
    }
  };

  const fetchChatMessages = async (shopId) => {
    if (!session?.access_token || !shopId) return;
    try {
      const res = await fetch(`${backendUrl}/api/chat/messages?shop_id=${shopId}`, {
        headers: { 'Authorization': `Bearer ${session.access_token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setMessages(data);
      }
    } catch (err) {
      console.error("Error fetching chat messages:", err);
    }
  };

  const handleShopSelect = (shop) => {
    setSelectedShop(shop);
    selectedShopRef.current = shop;
    localStorage.setItem('customer_selected_shop_id', shop.id.toString());
    setExtractedItems(null);
    fetchShopCatalog(shop.id);
    fetchCustomerOrders();
    fetchChatMessages(shop.id);
  };

  const handleAddCatalogProductToOrder = (productId) => {
    if (!productId) return;
    const prod = shopCatalog.find(p => p.id === parseInt(productId));
    if (!prod) return;

    setExtractedItems(prev => {
      const currentList = prev || [];
      const existingIdx = currentList.findIndex(item => item.matched_product_id === prod.id);
      if (existingIdx >= 0) {
        const updated = [...currentList];
        updated[existingIdx].quantity += 1;
        return updated;
      }
      return [
        ...currentList,
        {
          original_name: prod.name,
          matched_product_id: prod.id,
          matched_product_name: prod.name,
          matched_product_price: prod.price,
          quantity: 1.0,
          unit: prod.unit,
          recognized: true,
          suggestions: []
        }
      ];
    });
  };

  const handleItemQtyStep = (index, delta) => {
    setExtractedItems(prev => {
      if (!prev) return prev;
      const updated = [...prev];
      const newQty = Math.max(0.1, (parseFloat(updated[index].quantity) || 0) + delta);
      updated[index].quantity = Math.round(newQty * 10) / 10;
      return updated;
    });
  };

  const handleItemQtyChange = (index, value) => {
    setExtractedItems(prev => {
      if (!prev) return prev;
      const updated = [...prev];
      updated[index].quantity = parseFloat(value) || 0;
      return updated;
    });
  };

  const handleItemSuggestionChange = (index, suggestionId) => {
    setExtractedItems(prev => {
      if (!prev) return prev;
      const updated = [...prev];
      const item = updated[index];
      const match = item.suggestions?.find(s => s.id === parseInt(suggestionId));
      if (match) {
        item.matched_product_id = match.id;
        item.matched_product_name = match.name;
        item.matched_product_price = match.price;
        item.recognized = true;
      }
      return updated;
    });
  };

  const handleRemoveExtractedItem = (index) => {
    setExtractedItems(prev => prev.filter((_, idx) => idx !== index));
  };

  const handleSendText = async (e) => {
    e.preventDefault();
    if (!inputText.trim() || !selectedShop) return;

    const text = inputText;
    setInputText('');

    const userMsg = {
      id: Date.now(),
      sender_role: 'customer',
      message: text,
      created_at: new Date().toISOString()
    };
    setMessages(prev => [...prev, userMsg]);
    saveChatMessage(selectedShop.id, 'customer', text);
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
        const count = data.extracted_items?.length || 0;
        const botReply = {
          id: Date.now() + 1,
          sender_role: 'bot',
          message: count > 0
            ? `I extracted ${count} item(s) from your shopping list! Please review and adjust the order draft below.`
            : `I could not recognize items from your request. Please try typing item names like "2kg rice, 1 milk" or choose products from the Shop Products sidebar.`,
          created_at: new Date().toISOString()
        };
        setMessages(prev => [...prev, botReply]);
        saveChatMessage(selectedShop.id, 'bot', botReply.message);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleImageUpload = async (e) => {
    const file = e.target.files[0];
    if (!file || !selectedShop) return;

    const uploadText = `📷 Uploaded shopping list image: ${file.name}`;
    const userMsg = {
      id: Date.now(),
      sender_role: 'customer',
      message: uploadText,
      created_at: new Date().toISOString()
    };
    setMessages(prev => [...prev, userMsg]);
    saveChatMessage(selectedShop.id, 'customer', uploadText);
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
        setExtractedItems(data.extracted_items);
        const count = data.extracted_items?.length || 0;
        const botReply = {
          id: Date.now() + 1,
          sender_role: 'bot',
          message: count > 0
            ? `Extracted ${count} item(s) from your handwritten image! Please review and confirm your order draft below.`
            : `Could not clearly detect items in the image. Please try uploading a clearer image or type the items.`,
          created_at: new Date().toISOString()
        };
        setMessages(prev => [...prev, botReply]);
        saveChatMessage(selectedShop.id, 'bot', botReply.message);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleCreateDraftOrder = async () => {
    if (!extractedItems || extractedItems.length === 0) return;

    const validItems = extractedItems.filter(item => item.recognized);
    if (validItems.length === 0) return;

    setLoading(true);
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
        await fetchCustomerOrders();
        const botReply = {
          id: Date.now() + 2,
          sender_role: 'bot',
          message: `🎉 Order #${orderData.order_number || orderData.id} has been created and sent to the shop owner! Total: ₹${orderData.total_amount?.toFixed(2)}.`,
          created_at: new Date().toISOString()
        };
        setMessages(prev => [...prev, botReply]);
        saveChatMessage(selectedShop.id, 'bot', botReply.message);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  // Load the official Razorpay Checkout.js script once (idempotent)
  const loadRazorpayScript = () => {
    return new Promise((resolve) => {
      if (window.Razorpay) {
        resolve(true);
        return;
      }
      const script = document.createElement('script');
      script.src = 'https://checkout.razorpay.com/v1/checkout.js';
      script.async = true;
      script.onload = () => resolve(true);
      script.onerror = () => {
        console.error('[ChatBot] Failed to load Razorpay Checkout.js');
        resolve(false);
      };
      document.body.appendChild(script);
    });
  };

  const handleInitiatePaymentForOrder = async (ord, method) => {
    setLoading(true);
    try {
      if (method === 'razorpay') {
        // Step 1: Ask backend to create a Razorpay order
        const res = await fetch(`${backendUrl}/api/payments/create-razorpay-order/${ord.id}`, {
          method: 'POST',
          headers: { 'Authorization': `Bearer ${session.access_token}` }
        });

        if (!res.ok) {
          const errData = await res.json().catch(() => ({}));
          alert(`Cannot initiate payment: ${errData.detail || 'Server error'}`);
          return;
        }

        const data = await res.json();
        setPaymentDetails(data);
        setActivePaymentOrderId(ord.id);

        // Step 2: Load the official Razorpay Checkout.js
        const scriptLoaded = await loadRazorpayScript();

        if (!scriptLoaded || !window.Razorpay) {
          // Checkout.js failed to load (e.g. no internet / blocked) —
          // fall back to the test/demo QR display so offline dev still works
          console.warn('[ChatBot] Razorpay Checkout.js unavailable; showing stub QR panel.');
          setShowPayment(true);
          return;
        }

        // Check if this is stub mode (no real key configured)
        const isStubMode = !data.key_id || data.key_id === 'rzp_test_placeholder_id';
        if (isStubMode) {
          // Placeholder credentials — show the test demo panel
          console.info('[ChatBot] Stub Razorpay mode: real key not configured. Showing test demo panel.');
          setShowPayment(true);
          return;
        }

        setLoading(false); // Don't block UI while modal is open

        // Step 3: Open Razorpay Checkout modal
        const options = {
          key: data.key_id,                      // Public key (rzp_test_... or rzp_live_...)
          amount: data.amount_paise,              // In paise
          currency: data.currency || 'INR',
          name: 'RetailAutomate',
          description: `Order #${ord.shop_order_number || ord.id}`,
          order_id: data.razorpay_order_id,       // Razorpay order ID from backend

          handler: async function (response) {
            // Step 4: Submit the checkout response to backend for authoritative verification
            setLoading(true);
            try {
              const verifyRes = await fetch(`${backendUrl}/api/payments/verify-razorpay-signature`, {
                method: 'POST',
                headers: {
                  'Content-Type': 'application/json',
                  'Authorization': `Bearer ${session.access_token}`
                },
                body: JSON.stringify({
                  order_id: ord.id,
                  razorpay_order_id: response.razorpay_order_id,
                  razorpay_payment_id: response.razorpay_payment_id,
                  razorpay_signature: response.razorpay_signature
                })
              });

              if (verifyRes.ok) {
                // Payment confirmed by backend
                confetti({ particleCount: 150, spread: 80, origin: { y: 0.6 } });
                setShowPayment(false);
                setActivePaymentOrderId(null);
                setPaymentDetails(null);
                await fetchCustomerOrders();
              } else {
                const errData = await verifyRes.json().catch(() => ({}));
                alert(`Payment verification failed: ${errData.detail || 'Please contact support.'}`);
              }
            } catch (err) {
              console.error('[ChatBot] Error verifying payment signature:', err);
              alert('Network error during payment verification. Please contact support.');
            } finally {
              setLoading(false);
            }
          },

          prefill: {
            name: session?.name || '',
            contact: session?.phone_number || ''
          },

          theme: { color: '#6366f1' },

          modal: {
            ondismiss: function () {
              console.log('[ChatBot] Razorpay checkout dismissed by user.');
              setShowPayment(false);
              setActivePaymentOrderId(null);
              setPaymentDetails(null);
              setLoading(false);
            }
          }
        };

        const rzp = new window.Razorpay(options);
        rzp.on('payment.failed', function (response) {
          console.error('[ChatBot] Razorpay payment failed:', response.error);
          alert(
            `Payment failed: ${response.error?.description || 'Unknown error'}. ` +
            `Error code: ${response.error?.code || 'N/A'}. Please try again.`
          );
          setShowPayment(false);
          setActivePaymentOrderId(null);
          setPaymentDetails(null);
          setLoading(false);
        });
        rzp.open();

      } else {
        // Cash payment
        const res = await fetch(`${backendUrl}/api/payments/initiate/${ord.id}?method=${method}`, {
          method: 'POST',
          headers: { 'Authorization': `Bearer ${session.access_token}` }
        });

        if (res.ok) {
          setShowPayment(false);
          setActivePaymentOrderId(null);
          await fetchCustomerOrders();
        } else {
          const errData = await res.json().catch(() => ({}));
          alert(`Cash payment initiation failed: ${errData.detail || 'Server error'}`);
        }
      }
    } catch (err) {
      console.error('[ChatBot] Payment initiation error:', err);
      alert('Network error. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  // Dev/test helper: simulate payment success when real Razorpay credentials are not configured.
  // This path is ONLY reached when Checkout.js loads but key_id is a placeholder,
  // or when Checkout.js fails to load. It calls /demo-payment-success (dev-only endpoint).
  const handleSimulatePaymentForOrder = async (ord) => {
    if (!paymentDetails || !paymentDetails.razorpay_order_id) return;
    setLoading(true);
    try {
      const res = await fetch(`${backendUrl}/api/payments/demo-payment-success`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${session.access_token}`
        },
        body: JSON.stringify({
          order_id: ord.id,
          razorpay_order_id: paymentDetails.razorpay_order_id,
          razorpay_payment_id: `pay_demo_${Date.now()}`
        })
      });

      if (res.ok) {
        confetti({ particleCount: 150, spread: 80, origin: { y: 0.6 } });
        setShowPayment(false);
        setActivePaymentOrderId(null);
        setPaymentDetails(null);
        await fetchCustomerOrders();
      } else {
        const errData = await res.json().catch(() => ({}));
        alert(`Demo simulation failed: ${errData.detail || 'Server error'}`);
      }
    } catch (err) {
      console.error('[ChatBot] Error during demo payment simulation:', err);
    } finally {
      setLoading(false);
    }
  };


  const filteredShopCatalog = shopCatalog.filter(p =>
    p.name.toLowerCase().includes(catalogSearchQuery.trim().toLowerCase())
  );

  return (
    <div className="customer-layout-wrapper">
      {/* Main Chat / Orders Window */}
      <div className="chat-container">
        {/* Top Header & Shop Selector */}
        <div className="chat-header">
          <div>
            <span className="chat-title">💬 Multimodal AI Shopping Assistant</span>
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
              value={selectedShop?.id || ""}
            >
              <option value="" disabled>🏪 Choose a Shop...</option>
              {shops.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
          </div>
        </div>

        {/* Customer Orders Area (No tab switcher, no chat bubbles) */}
        <div className="chat-messages" style={{ display: 'flex', flexDirection: 'column', gap: '16px', padding: '16px' }}>

          {/* Interactive Order Editing Card */}
          {extractedItems && (
            <div className="order-extraction-card" style={{ borderColor: 'var(--primary)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px', flexWrap: 'wrap', gap: '8px' }}>
                <h4 style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '14px', margin: 0, color: 'var(--primary)' }}>
                  <ShoppingBag size={16} /> Edit & Review Order Items
                </h4>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', maxWidth: '100%' }}>
                  <select
                    className="suggestions-select"
                    style={{ padding: '4px 8px', fontSize: '12px', maxWidth: '100%' }}
                    value=""
                    onChange={(e) => {
                      if (e.target.value) {
                        handleAddCatalogProductToOrder(e.target.value);
                        e.target.value = "";
                      }
                    }}
                  >
                    <option value="" disabled>➕ Add Product from Catalog...</option>
                    {shopCatalog.map(p => (
                      <option key={p.id} value={p.id}>{p.name} (₹{p.price}/{p.unit})</option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="table-responsive">
                <table className="premium-table order-items-table" style={{ fontSize: '12px', marginBottom: '10px' }}>
                  <thead>
                    <tr>
                      <th>Item Name</th>
                      <th>Quantity</th>
                      <th>Price / Unit</th>
                      <th>Item Total</th>
                      <th>Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {extractedItems.map((item, idx) => {
                      const price = item.matched_product_price || 0;
                      const itemTotal = (parseFloat(item.quantity) || 0) * price;
                      return (
                        <tr key={idx}>
                          <td>
                            <div style={{ fontWeight: '600' }}>{item.matched_product_name || item.original_name}</div>
                            {!item.recognized && item.suggestions?.length > 0 && (
                              <select
                                className="suggestions-select"
                                style={{ marginTop: '4px', fontSize: '11px' }}
                                onChange={(e) => handleItemSuggestionChange(idx, e.target.value)}
                                defaultValue=""
                              >
                                <option value="" disabled>Select match from catalog...</option>
                                {item.suggestions.map(s => (
                                  <option key={s.id} value={s.id}>{s.name} (₹{s.price})</option>
                                ))}
                              </select>
                            )}
                          </td>
                          <td>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                              <button
                                type="button"
                                className="btn-logout"
                                style={{ padding: '2px 6px', fontSize: '11px', fontWeight: '700' }}
                                onClick={() => handleItemQtyStep(idx, -1)}
                              >
                                -
                              </button>
                              <input
                                type="number"
                                className="form-input"
                                style={{ padding: '3px 6px', fontSize: '12px', width: '55px', textAlign: 'center' }}
                                value={item.quantity}
                                onChange={(e) => handleItemQtyChange(idx, e.target.value)}
                                step="0.5"
                                min="0.1"
                              />
                              <button
                                type="button"
                                className="btn-logout"
                                style={{ padding: '2px 6px', fontSize: '11px', fontWeight: '700' }}
                                onClick={() => handleItemQtyStep(idx, 1)}
                              >
                                +
                              </button>
                              <span style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>{item.unit}</span>
                            </div>
                          </td>
                          <td>₹{price > 0 ? price.toFixed(2) : '-'}</td>
                          <td style={{ fontWeight: '700', color: 'var(--primary)' }}>
                            {price > 0 ? `₹${itemTotal.toFixed(2)}` : '-'}
                          </td>
                          <td>
                            <button
                              type="button"
                              className="btn-close-alert"
                              style={{ color: 'var(--error)', display: 'flex', alignItems: 'center', gap: '4px', fontSize: '12px' }}
                              onClick={() => handleRemoveExtractedItem(idx)}
                            >
                              <Trash2 size={14} /> Remove
                            </button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>

              {/* Automatic Grand Total */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '12px', paddingTop: '10px', borderTop: '1px solid var(--surface-border)', flexWrap: 'wrap', gap: '10px' }}>
                <span style={{ fontSize: '14px', fontWeight: '800' }}>
                  Grand Total: ₹{extractedItems.reduce((sum, i) => sum + ((parseFloat(i.quantity) || 0) * (i.matched_product_price || 0)), 0).toFixed(2)}
                </span>
                <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                  <button className="btn-primary" style={{ padding: '8px 16px', fontSize: '13px', width: 'auto' }} onClick={handleCreateDraftOrder}>
                    Confirm Order & Send to Owner
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
            </div>
          )}

          {/* Conversation Messages */}
          {selectedShop && (
            messages.length === 0 ? (
              <div className="chat-bubble bot" style={{ alignSelf: 'flex-start', maxWidth: '85%' }}>
                <div>
                  👋 Welcome to <strong>{selectedShop.name}</strong>! You can chat with me, type your grocery list (e.g. <em>2kg Rice, 1 Milk</em>), upload a picture of a handwritten list, or select items from <strong>Shop Products</strong> on the right to start an order.
                </div>
              </div>
            ) : (
              messages.map((m, idx) => (
                <div
                  key={m.id || idx}
                  className={`chat-bubble ${m.sender_role === 'customer' || m.sender_role === 'user' ? 'user' : 'bot'}`}
                  style={{
                    alignSelf: m.sender_role === 'customer' || m.sender_role === 'user' ? 'flex-end' : 'flex-start',
                    maxWidth: '85%'
                  }}
                >
                  <div>{m.message}</div>
                  {m.created_at && (
                    <div style={{
                      fontSize: '10px',
                      opacity: 0.7,
                      marginTop: '4px',
                      textAlign: m.sender_role === 'customer' || m.sender_role === 'user' ? 'right' : 'left'
                    }}>
                      {formatDateTime(m.created_at)}
                    </div>
                  )}
                </div>
              ))
            )
          )}

          {!selectedShop && (
            <div style={{ padding: '60px 20px', textAlign: 'center', color: 'var(--text-secondary)' }}>
              <Store size={48} style={{ opacity: 0.4, marginBottom: '12px' }} />
              <h3 style={{ fontSize: '16px', color: 'var(--text-primary)', marginBottom: '6px' }}>No Shop Selected</h3>
              <p style={{ fontSize: '13px', margin: 0 }}>Please select a shop from the dropdown above to view products and place an order.</p>
            </div>
          )}

          {/* Current Newly Created / Active Order Card */}
          {currentOrder && (
            <div
              className="order-extraction-card"
              style={{
                marginBottom: '0',
                borderColor: currentOrder.payment_status === 'paid' ? '#10b981' : 'var(--primary)'
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px', flexWrap: 'wrap', gap: '6px' }}>
                <span style={{ fontWeight: '800', fontSize: '15px', color: 'var(--primary)' }}>
                  Current Order #{currentOrder.order_number || currentOrder.id}
                </span>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>
                    {formatDateTime(currentOrder.created_at)}
                  </span>
                  <button
                    type="button"
                    className="btn-logout"
                    style={{ padding: '2px 8px', fontSize: '11px' }}
                    onClick={() => setCurrentOrder(null)}
                    title="Close current order card"
                  >
                    ✕ Close Card
                  </button>
                </div>
              </div>

              <div style={{ display: 'flex', gap: '8px', marginBottom: '10px', flexWrap: 'wrap' }}>
                <span className={`badge-status ${currentOrder.status}`} style={{ fontSize: '11px', textTransform: 'capitalize' }}>
                  Status: {currentOrder.status ? currentOrder.status.replace('_', ' ') : 'Pending'}
                </span>
                <span className="badge-status pending" style={{
                  fontSize: '11px',
                  textTransform: 'capitalize',
                  backgroundColor: currentOrder.payment_status === 'paid' ? '#d4edda' : '#fff3cd',
                  color: currentOrder.payment_status === 'paid' ? '#155724' : '#856404'
                }}>
                  Payment: {currentOrder.payment_status ? currentOrder.payment_status.replace('_', ' ') : 'Not Paid'}
                </span>
              </div>

              <div style={{ margin: '10px 0' }}>
                <div style={{ fontWeight: '700', fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '6px' }}>
                  📦 Ordered Items:
                </div>
                <div className="table-responsive">
                  <table className="premium-table order-items-table" style={{ width: '100%', fontSize: '12px', marginBottom: '8px' }}>
                    <thead>
                      <tr>
                        <th style={{ textAlign: 'left', padding: '6px 8px' }}>Product</th>
                        <th style={{ textAlign: 'center', padding: '6px 8px' }}>Quantity</th>
                        <th style={{ textAlign: 'right', padding: '6px 8px' }}>Price / Unit</th>
                        <th style={{ textAlign: 'right', padding: '6px 8px' }}>Item Total</th>
                      </tr>
                    </thead>
                    <tbody>
                      {currentOrder.items && currentOrder.items.length > 0 ? (
                        currentOrder.items.map((it, idx) => {
                          const price = it.price_at_order || 0;
                          const itemTotal = (it.quantity || 0) * price;
                          return (
                            <tr key={it.id || idx}>
                              <td style={{ fontWeight: '600', padding: '6px 8px' }}>{it.product_name}</td>
                              <td style={{ textAlign: 'center', padding: '6px 8px' }}>{it.quantity} {it.unit || ''}</td>
                              <td style={{ textAlign: 'right', padding: '6px 8px' }}>₹{price.toFixed(2)}</td>
                              <td style={{ textAlign: 'right', fontWeight: '700', color: 'var(--primary)', padding: '6px 8px' }}>
                                ₹{itemTotal.toFixed(2)}
                              </td>
                            </tr>
                          );
                        })
                      ) : (
                        <tr>
                          <td colSpan="4" style={{ textAlign: 'center', color: 'var(--text-secondary)', padding: '8px' }}>No items</td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </div>

              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', paddingTop: '8px', borderTop: '1px solid var(--surface-border)', flexWrap: 'wrap', gap: '8px' }}>
                <span style={{ fontSize: '14px', fontWeight: '800', color: 'var(--text-primary)' }}>
                  Total: ₹{currentOrder.total_amount?.toFixed(2)}
                </span>
                {currentOrder.payment_status === 'paid' && (
                  <span style={{ fontSize: '12px', fontWeight: '700', color: '#10b981' }}>
                    ✓ Paid Successfully
                  </span>
                )}
              </div>

              {/* Payment Action Buttons for Unpaid Orders */}
              {currentOrder.payment_status !== 'paid' && currentOrder.status !== 'rejected' && currentOrder.status !== 'deleted' && (
                <div style={{ marginTop: '12px', paddingTop: '10px', borderTop: '1px dashed var(--surface-border)' }}>
                  {currentOrder.payment_status === 'cash_pending' || currentOrder.payment_method === 'cash' ? (
                    <div style={{ backgroundColor: '#fff3cd', color: '#856404', padding: '8px 12px', borderRadius: '4px', fontSize: '12px', fontWeight: '600' }}>
                      💵 Cash Payment Selected (Status: Cash Pending). Please pay ₹{currentOrder.total_amount?.toFixed(2)} directly to shop owner.
                    </div>
                  ) : (
                    <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                      <button
                        className="btn-primary"
                        style={{ padding: '6px 12px', fontSize: '12px', backgroundColor: 'var(--secondary)', width: 'auto' }}
                        onClick={() => handleInitiatePaymentForOrder(currentOrder, 'razorpay')}
                      >
                        Pay Online (Razorpay)
                      </button>
                      <button
                        className="btn-logout"
                        style={{ padding: '6px 12px', fontSize: '12px', borderColor: 'var(--text-secondary)', width: 'auto' }}
                        onClick={() => handleInitiatePaymentForOrder(currentOrder, 'cash')}
                      >
                        Pay Cash at Shop
                      </button>
                    </div>
                  )}

                  {/* Razorpay Payment / QR Box */}
                  {showPayment && paymentDetails && activePaymentOrderId === currentOrder.id && (
                    <div className="qr-modal" style={{ marginTop: '12px' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <h4 style={{ fontSize: '13px', margin: 0 }}>📱 Pay Online via Razorpay</h4>
                        <button
                          type="button"
                          className="btn-logout"
                          style={{ padding: '2px 8px', fontSize: '11px' }}
                          onClick={() => {
                            setShowPayment(false);
                            setActivePaymentOrderId(null);
                            setPaymentDetails(null);
                          }}
                        >
                          Close
                        </button>
                      </div>
                      <div style={{ fontSize: '15px', fontWeight: '800', color: 'var(--primary)', marginTop: '4px' }}>₹{paymentDetails.amount}</div>

                      {paymentDetails.upi_uri && (
                        <img
                          src={`https://api.qrserver.com/v1/create-qr-code/?size=150x150&data=${encodeURIComponent(paymentDetails.upi_uri)}`}
                          alt="Razorpay Test QR"
                          style={{ margin: '10px 0', border: '1px solid var(--surface-border)', padding: '4px', borderRadius: '4px' }}
                        />
                      )}

                      <p style={{ fontSize: '11px', color: 'var(--text-secondary)', marginBottom: '8px' }}>
                        Razorpay Order ID: <span style={{ fontFamily: 'monospace' }}>{paymentDetails.razorpay_order_id}</span>
                      </p>

                      <button
                        className="btn-primary"
                        style={{ width: '100%', fontSize: '12px' }}
                        onClick={() => handleSimulatePaymentForOrder(currentOrder)}
                      >
                        Simulate Razorpay Payment Success (Demo)
                      </button>
                    </div>
                  )}
                </div>
              )}
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

          <form onSubmit={handleSendText} className="chat-input-form" style={{ display: 'flex', flex: 1, gap: '8px', minWidth: 0 }}>
            <input
              type="text"
              className="chat-text-area"
              placeholder={selectedShop ? "Type items list here (e.g. 2kg rice, 1 milk)..." : "Please select a shop first"}
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

      {/* Dedicated Customer Product Sidebar */}
      {selectedShop && (
        <div className="customer-product-sidebar">
          <div className="sidebar-catalog-header">
            <div style={{ fontWeight: '700', fontSize: '14px', color: 'var(--primary)', display: 'flex', alignItems: 'center', gap: '6px' }}>
              <Store size={18} /> Shop Products ({filteredShopCatalog.length})
            </div>
            <div style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>{selectedShop.name}</div>
          </div>

          {/* Instant Search Input */}
          <div style={{ padding: '10px 14px', borderBottom: '1px solid var(--surface-border)', backgroundColor: 'var(--surface)' }}>
            <input
              type="text"
              className="form-input"
              style={{ padding: '6px 12px', fontSize: '13px' }}
              placeholder="🔍 Search product name..."
              value={catalogSearchQuery}
              onChange={(e) => setCatalogSearchQuery(e.target.value)}
            />
          </div>

          {/* Scrollable Product Cards List */}
          <div className="sidebar-catalog-list">
            {filteredShopCatalog.length === 0 ? (
              <div style={{ padding: '20px', textAlign: 'center', fontSize: '12px', color: 'var(--text-secondary)' }}>
                {catalogSearchQuery.trim() ? "No products match your search." : "No products available in this shop catalog."}
              </div>
            ) : (
              filteredShopCatalog.map(p => (
                <div key={p.id} className="catalog-product-item">
                  <div style={{ flex: 1 }}>
                    <div style={{ fontWeight: '600', fontSize: '13px', color: 'var(--text-primary)' }}>{p.name}</div>
                    <div style={{ fontSize: '12px', color: 'var(--primary)', fontWeight: '700', marginTop: '2px' }}>
                      ₹{p.price.toFixed(2)} / {p.unit}
                    </div>
                  </div>
                  <button
                    type="button"
                    className="btn-primary"
                    style={{ padding: '4px 10px', fontSize: '12px', width: 'auto' }}
                    onClick={() => handleAddCatalogProductToOrder(p.id)}
                  >
                    + Add
                  </button>
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}
