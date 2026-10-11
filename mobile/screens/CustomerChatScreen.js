import React, { useState, useEffect, useRef } from 'react';
import {
  View, Text, TextInput, TouchableOpacity, FlatList,
  StyleSheet, ActivityIndicator, ScrollView, Image, Modal,
  Alert, KeyboardAvoidingView, Platform,
} from 'react-native';
import { Feather } from '@expo/vector-icons';
import * as ImagePicker from 'expo-image-picker';

import { colors, sharedStyles, radius, getStatusColors } from '../styles/theme';
import { BACKEND_URL, getWebSocketUrl } from '../firebaseConfig';
import { getItem, setItem } from '../utils/storage';
import { formatDateTime } from '../utils/dateTimeUtils';

export default function CustomerChatScreen({ session, onLogout }) {
  const [shops, setShops] = useState([]);
  const [selectedShop, setSelectedShop] = useState(null);
  const [shopCatalog, setShopCatalog] = useState([]);
  const [customerOrders, setCustomerOrders] = useState([]);

  const [inputText, setInputText] = useState('');
  const [loading, setLoading] = useState(false);

  const [extractedItems, setExtractedItems] = useState(null);
  const [currentOrder, setCurrentOrder] = useState(null);
  const [showPayment, setShowPayment] = useState(false);
  const [paymentDetails, setPaymentDetails] = useState(null);
  const [activePaymentOrderId, setActivePaymentOrderId] = useState(null);
  const [isConnected, setIsConnected] = useState(false);

  // UI modals
  const [shopModalVisible, setShopModalVisible] = useState(false);
  const [catalogModalVisible, setCatalogModalVisible] = useState(false);

  const socketRef = useRef(null);
  const reconnectTimerRef = useRef(null);
  const isMountedRef = useRef(true);

  // ─── WebSocket ──────────────────────────────────────────────────────────────
  useEffect(() => {
    isMountedRef.current = true;
    connectWebSocket();
    return () => {
      isMountedRef.current = false;
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
      if (socketRef.current) {
        try { socketRef.current.close(); } catch (e) {}
      }
    };
  }, [session?.user_id]);

  const connectWebSocket = () => {
    if (!session?.user_id) return;
    const wsUrl = getWebSocketUrl(BACKEND_URL, session.user_id);
    const socket = new WebSocket(wsUrl);
    socketRef.current = socket;

    socket.onopen = () => {
      if (isMountedRef.current) setIsConnected(true);
    };
    socket.onmessage = (event) => {
      if (!isMountedRef.current) return;
      try {
        const data = JSON.parse(event.data);
        if (['order_reviewed', 'order_rejected', 'order_deleted'].includes(data.type)) {
          fetchCustomerOrders();
        }
        if (data.type === 'payment_success') {
          setShowPayment(false);
          setActivePaymentOrderId(null);
          fetchCustomerOrders();
          Alert.alert('🎉 Payment Successful!', 'Your order has been paid.');
        }
      } catch (e) {}
    };
    socket.onerror = () => {
      if (isMountedRef.current) setIsConnected(false);
    };
    socket.onclose = () => {
      if (isMountedRef.current) {
        setIsConnected(false);
        reconnectTimerRef.current = setTimeout(() => {
          if (isMountedRef.current) connectWebSocket();
        }, 3000);
      }
    };
  };

  // ─── Data fetching ───────────────────────────────────────────────────────────
  useEffect(() => {
    fetchShops();
    fetchCustomerOrders();
  }, []);

  const fetchShops = async () => {
    try {
      const res = await fetch(`${BACKEND_URL}/api/shops/`);
      if (res.ok) {
        const data = await res.json();
        setShops(data);
        // Restore previously selected shop
        const savedId = await getItem('customer_selected_shop_id');
        if (savedId && data.length > 0) {
          const matched = data.find(s => s.id === parseInt(savedId));
          if (matched) handleShopSelect(matched);
        }
      }
    } catch (e) { console.error(e); }
  };

  const fetchShopCatalog = async (shopId) => {
    try {
      const res = await fetch(`${BACKEND_URL}/api/products/?shop_id=${shopId}`);
      if (res.ok) setShopCatalog(await res.json());
    } catch (e) { console.error(e); }
  };

  const fetchCustomerOrders = async () => {
    if (!session?.access_token) return;
    try {
      const res = await fetch(`${BACKEND_URL}/api/orders/`, {
        headers: { 'Authorization': `Bearer ${session.access_token}` },
      });
      if (res.ok) setCustomerOrders(await res.json());
    } catch (e) { console.error(e); }
  };

  const handleShopSelect = (shop) => {
    setSelectedShop(shop);
    setItem('customer_selected_shop_id', shop.id.toString());
    setExtractedItems(null);
    fetchShopCatalog(shop.id);
    fetchCustomerOrders();
    setShopModalVisible(false);
  };

  // ─── Text order processing ──────────────────────────────────────────────────
  const handleSendText = async () => {
    if (!inputText.trim() || !selectedShop) return;
    const text = inputText;
    setInputText('');
    setLoading(true);
    try {
      const formData = new FormData();
      formData.append('text', text);
      const res = await fetch(
        `${BACKEND_URL}/api/orders/process-text?shop_id=${selectedShop.id}`,
        {
          method: 'POST',
          headers: { 'Authorization': `Bearer ${session.access_token}` },
          body: formData,
        }
      );
      if (res.ok) {
        const data = await res.json();
        setExtractedItems(data.extracted_items);
      }
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  };

  // ─── Image upload (OCR) ──────────────────────────────────────────────────────
  const handleImageUpload = async () => {
    if (!selectedShop) {
      Alert.alert('No shop selected', 'Please select a shop first.');
      return;
    }
    const { status } = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (status !== 'granted') {
      Alert.alert('Permission needed', 'Allow access to photos to upload a shopping list image.');
      return;
    }
    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ImagePicker.MediaTypeOptions.Images,
      quality: 0.8,
    });
    if (result.canceled || !result.assets?.length) return;

    const asset = result.assets[0];
    setLoading(true);
    try {
      const formData = new FormData();
      formData.append('file', {
        uri: asset.uri,
        name: 'shopping_list.jpg',
        type: 'image/jpeg',
      });
      const res = await fetch(
        `${BACKEND_URL}/api/orders/process-image?shop_id=${selectedShop.id}`,
        {
          method: 'POST',
          headers: { 'Authorization': `Bearer ${session.access_token}` },
          body: formData,
        }
      );
      if (res.ok) {
        const data = await res.json();
        setExtractedItems(data.extracted_items);
      }
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  };

  // ─── Order editing ───────────────────────────────────────────────────────────
  const handleItemQtyStep = (index, delta) => {
    setExtractedItems(prev => {
      if (!prev) return prev;
      const updated = [...prev];
      const newQty = Math.max(0.1, (parseFloat(updated[index].quantity) || 0) + delta);
      updated[index] = { ...updated[index], quantity: Math.round(newQty * 10) / 10 };
      return updated;
    });
  };

  const handleRemoveItem = (index) => {
    setExtractedItems(prev => prev.filter((_, i) => i !== index));
  };

  const addFromCatalog = (product) => {
    setExtractedItems(prev => {
      const list = prev || [];
      const idx = list.findIndex(i => i.matched_product_id === product.id);
      if (idx >= 0) {
        const updated = [...list];
        updated[idx] = { ...updated[idx], quantity: updated[idx].quantity + 1 };
        return updated;
      }
      return [
        ...list,
        {
          original_name: product.name,
          matched_product_id: product.id,
          matched_product_name: product.name,
          matched_product_price: product.price,
          quantity: 1.0,
          unit: product.unit,
          recognized: true,
          suggestions: [],
        },
      ];
    });
    setCatalogModalVisible(false);
  };

  // ─── Create draft order ──────────────────────────────────────────────────────
  const handleCreateDraftOrder = async () => {
    if (!extractedItems?.length) return;
    const validItems = extractedItems.filter(i => i.recognized);
    if (!validItems.length) return;

    setLoading(true);
    try {
      const payload = {
        shop_id: selectedShop.id,
        items: validItems.map(i => ({
          product_id: i.matched_product_id,
          quantity: i.quantity,
          unit: i.unit,
          price_at_order: i.matched_product_price,
        })),
        notes: 'Created via Mobile AI Shopping Assistant',
      };
      const res = await fetch(`${BACKEND_URL}/api/orders/create-draft`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${session.access_token}`,
        },
        body: JSON.stringify(payload),
      });
      if (res.ok) {
        setCurrentOrder(await res.json());
        setExtractedItems(null);
        fetchCustomerOrders();
        Alert.alert('✅ Order Sent', 'Your order has been sent to the shop owner for review.');
      }
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  };

  // ─── Payment ─────────────────────────────────────────────────────────────────
  const handleInitiatePayment = async (ord, method) => {
    setLoading(true);
    try {
      if (method === 'razorpay') {
        const res = await fetch(
          `${BACKEND_URL}/api/payments/create-razorpay-order/${ord.id}`,
          { method: 'POST', headers: { 'Authorization': `Bearer ${session.access_token}` } }
        );
        if (res.ok) {
          const data = await res.json();
          setPaymentDetails(data);
          setActivePaymentOrderId(ord.id);
          setShowPayment(true);
        }
      } else {
        const res = await fetch(
          `${BACKEND_URL}/api/payments/initiate/${ord.id}?method=${method}`,
          { method: 'POST', headers: { 'Authorization': `Bearer ${session.access_token}` } }
        );
        if (res.ok) {
          setShowPayment(false);
          setActivePaymentOrderId(null);
          fetchCustomerOrders();
          Alert.alert('Cash Payment', 'Cash payment selected. Please pay at the shop.');
        }
      }
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  };

  const handleSimulateWebhook = async (ord) => {
    if (!paymentDetails?.razorpay_order_id) return;
    setLoading(true);
    try {
      const res = await fetch(`${BACKEND_URL}/api/payments/webhook`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'x-razorpay-signature': 'sandbox_bypass',
          'Authorization': `Bearer ${session.access_token}`,
        },
        body: JSON.stringify({
          event: 'order.paid',
          order_id: ord.id,
          razorpay_order_id: paymentDetails.razorpay_order_id,
          payload: {
            order: { entity: { id: paymentDetails.razorpay_order_id } },
            payment: { entity: { id: 'pay_simulated_' + Math.random().toString(36).substr(2, 9) } },
          },
        }),
      });
      if (res.ok) {
        setShowPayment(false);
        setActivePaymentOrderId(null);
        fetchCustomerOrders();
        Alert.alert('🎉 Payment Successful!', 'Your payment has been simulated successfully.');
      }
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  };

  const displayOrders = selectedShop
    ? customerOrders.filter(o => o.shop_id === selectedShop.id)
    : [];

  // ─── Grand total ─────────────────────────────────────────────────────────────
  const grandTotal = extractedItems
    ? extractedItems.reduce((sum, i) => sum + ((parseFloat(i.quantity) || 0) * (i.matched_product_price || 0)), 0)
    : 0;

  // ─── Render ──────────────────────────────────────────────────────────────────
  return (
    <View style={sharedStyles.screen}>
      {/* Header */}
      <View style={sharedStyles.header}>
        <View style={{ flex: 1 }}>
          <Text style={sharedStyles.headerTitle}>💬 AI Shopping</Text>
          <Text style={sharedStyles.headerSubtitle}>
            {session.phone_number} • {isConnected ? '🟢 Live' : '🔴 Offline'}
          </Text>
        </View>
        <TouchableOpacity onPress={onLogout} style={styles.logoutBtn}>
          <Feather name="log-out" size={18} color="rgba(255,255,255,0.8)" />
        </TouchableOpacity>
      </View>

      {/* Shop selector bar */}
      <TouchableOpacity style={styles.shopBar} onPress={() => setShopModalVisible(true)}>
        <Feather name="shopping-bag" size={16} color={colors.primary} />
        <Text style={styles.shopBarText}>
          {selectedShop ? selectedShop.name : 'Select a Shop...'}
        </Text>
        <Feather name="chevron-down" size={16} color={colors.textSecondary} />
      </TouchableOpacity>

      {/* Main scroll */}
      <ScrollView style={{ flex: 1 }} contentContainerStyle={{ padding: 16 }}>

        {/* Extracted items / order editing card */}
        {extractedItems && (
          <View style={[sharedStyles.card, { borderColor: colors.primary, borderWidth: 2 }]}>
            <View style={[sharedStyles.sectionHeader]}>
              <Text style={sharedStyles.sectionTitle}>🛒 Review Your Order</Text>
              <TouchableOpacity onPress={() => setCatalogModalVisible(true)} style={styles.addFromCatalogBtn}>
                <Feather name="plus" size={14} color={colors.primary} />
                <Text style={styles.addFromCatalogText}>Add Product</Text>
              </TouchableOpacity>
            </View>

            {extractedItems.map((item, idx) => (
              <View key={idx} style={styles.orderItemRow}>
                <View style={{ flex: 1 }}>
                  <Text style={styles.orderItemName}>{item.matched_product_name || item.original_name}</Text>
                  {item.matched_product_price > 0 && (
                    <Text style={sharedStyles.smallText}>
                      ₹{item.matched_product_price}/{item.unit} •{' '}
                      <Text style={{ color: colors.primary, fontWeight: '700' }}>
                        ₹{((parseFloat(item.quantity) || 0) * item.matched_product_price).toFixed(2)}
                      </Text>
                    </Text>
                  )}
                </View>
                <View style={styles.qtyControls}>
                  <TouchableOpacity
                    style={styles.qtyBtn}
                    onPress={() => handleItemQtyStep(idx, -1)}
                  >
                    <Text style={styles.qtyBtnText}>−</Text>
                  </TouchableOpacity>
                  <Text style={styles.qtyValue}>{item.quantity} {item.unit}</Text>
                  <TouchableOpacity
                    style={styles.qtyBtn}
                    onPress={() => handleItemQtyStep(idx, 1)}
                  >
                    <Text style={styles.qtyBtnText}>+</Text>
                  </TouchableOpacity>
                </View>
                <TouchableOpacity onPress={() => handleRemoveItem(idx)} style={{ padding: 6 }}>
                  <Feather name="trash-2" size={16} color={colors.error} />
                </TouchableOpacity>
              </View>
            ))}

            <View style={[sharedStyles.divider]} />
            <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
              <Text style={{ fontSize: 15, fontWeight: '800', color: colors.textPrimary }}>
                Grand Total
              </Text>
              <Text style={{ fontSize: 17, fontWeight: '900', color: colors.primary }}>
                ₹{grandTotal.toFixed(2)}
              </Text>
            </View>

            <TouchableOpacity
              style={[sharedStyles.btnPrimary, loading && sharedStyles.btnDisabled]}
              onPress={handleCreateDraftOrder}
              disabled={loading}
            >
              {loading
                ? <ActivityIndicator color="#fff" />
                : <Text style={sharedStyles.btnPrimaryText}>✅ Confirm & Send to Owner</Text>}
            </TouchableOpacity>
            <TouchableOpacity
              style={sharedStyles.btnSecondary}
              onPress={() => setExtractedItems(null)}
            >
              <Text style={sharedStyles.btnSecondaryText}>Cancel</Text>
            </TouchableOpacity>
          </View>
        )}

        {/* Orders list */}
        {!selectedShop ? (
          <View style={sharedStyles.emptyContainer}>
            <Feather name="shopping-bag" size={48} color={colors.textMuted} />
            <Text style={sharedStyles.emptyText}>
              Select a shop from the bar above to view products and place an order.
            </Text>
          </View>
        ) : displayOrders.length === 0 && !extractedItems ? (
          <View style={sharedStyles.emptyContainer}>
            <Feather name="message-circle" size={48} color={colors.textMuted} />
            <Text style={sharedStyles.emptyText}>
              No orders at {selectedShop.name} yet.{'\n'}
              Type your shopping list below or upload a photo.
            </Text>
          </View>
        ) : (
          displayOrders.map(ord => (
            <OrderCard
              key={ord.id}
              ord={ord}
              onPayRazorpay={() => handleInitiatePayment(ord, 'razorpay')}
              onPayCash={() => handleInitiatePayment(ord, 'cash')}
              showPayment={showPayment && activePaymentOrderId === ord.id}
              paymentDetails={paymentDetails}
              onSimulatePayment={() => handleSimulateWebhook(ord)}
              loading={loading}
            />
          ))
        )}

        {loading && (
          <View style={{ alignItems: 'center', padding: 20 }}>
            <ActivityIndicator size="large" color={colors.primary} />
            <Text style={[sharedStyles.smallText, { marginTop: 8 }]}>AI is processing...</Text>
          </View>
        )}
      </ScrollView>

      {/* Input area */}
      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        <View style={styles.inputArea}>
          <TouchableOpacity
            style={styles.iconBtn}
            onPress={handleImageUpload}
            disabled={!selectedShop}
          >
            <Feather name="image" size={22} color={selectedShop ? colors.primary : colors.textMuted} />
          </TouchableOpacity>
          <TextInput
            style={styles.chatInput}
            placeholder={selectedShop ? 'Type your shopping list...' : 'Select a shop first'}
            value={inputText}
            onChangeText={setInputText}
            editable={!!selectedShop}
            onSubmitEditing={handleSendText}
            returnKeyType="send"
            multiline
          />
          <TouchableOpacity
            style={[styles.sendBtn, (!inputText.trim() || !selectedShop) && { opacity: 0.4 }]}
            onPress={handleSendText}
            disabled={!inputText.trim() || !selectedShop}
          >
            <Feather name="send" size={20} color="#fff" />
          </TouchableOpacity>
        </View>
      </KeyboardAvoidingView>

      {/* Shop picker modal */}
      <Modal visible={shopModalVisible} transparent animationType="slide">
        <View style={styles.modalOverlay}>
          <View style={styles.modalSheet}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>Select a Shop</Text>
              <TouchableOpacity onPress={() => setShopModalVisible(false)}>
                <Feather name="x" size={22} color={colors.textSecondary} />
              </TouchableOpacity>
            </View>
            <FlatList
              data={shops}
              keyExtractor={item => String(item.id)}
              renderItem={({ item }) => (
                <TouchableOpacity
                  style={styles.modalItem}
                  onPress={() => handleShopSelect(item)}
                >
                  <Feather name="shopping-bag" size={18} color={colors.primary} />
                  <Text style={styles.modalItemText}>{item.name}</Text>
                  {selectedShop?.id === item.id && (
                    <Feather name="check" size={18} color={colors.secondary} />
                  )}
                </TouchableOpacity>
              )}
              ItemSeparatorComponent={() => <View style={sharedStyles.divider} />}
            />
          </View>
        </View>
      </Modal>

      {/* Catalog picker modal */}
      <Modal visible={catalogModalVisible} transparent animationType="slide">
        <View style={styles.modalOverlay}>
          <View style={styles.modalSheet}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>Add from Catalog</Text>
              <TouchableOpacity onPress={() => setCatalogModalVisible(false)}>
                <Feather name="x" size={22} color={colors.textSecondary} />
              </TouchableOpacity>
            </View>
            <FlatList
              data={shopCatalog}
              keyExtractor={item => String(item.id)}
              renderItem={({ item }) => (
                <TouchableOpacity style={styles.modalItem} onPress={() => addFromCatalog(item)}>
                  <View style={{ flex: 1 }}>
                    <Text style={styles.modalItemText}>{item.name}</Text>
                    <Text style={sharedStyles.smallText}>
                      ₹{item.price}/{item.unit} • Stock: {item.stock}
                    </Text>
                  </View>
                  <Feather name="plus-circle" size={20} color={colors.primary} />
                </TouchableOpacity>
              )}
              ItemSeparatorComponent={() => <View style={sharedStyles.divider} />}
            />
          </View>
        </View>
      </Modal>
    </View>
  );
}

// ── Order Card Sub-component ──────────────────────────────────────────────────
function OrderCard({ ord, onPayRazorpay, onPayCash, showPayment, paymentDetails, onSimulatePayment, loading }) {
  const statusColors = getStatusColors(ord.status);
  const paymentColors = getStatusColors(ord.payment_status);

  return (
    <View style={sharedStyles.card}>
      <View style={{ flexDirection: 'row', justifyContent: 'space-between', marginBottom: 8 }}>
        <Text style={{ fontWeight: '800', fontSize: 15, color: colors.primary }}>
          Order #{ord.order_number || ord.id}
        </Text>
        <Text style={sharedStyles.smallText}>{formatDateTime(ord.created_at)}</Text>
      </View>

      <View style={{ flexDirection: 'row', gap: 8, marginBottom: 10 }}>
        <View style={[sharedStyles.badge, { backgroundColor: statusColors.bg }]}>
          <Text style={[sharedStyles.badgeText, { color: statusColors.text }]}>
            {(ord.status || 'pending').replace('_', ' ')}
          </Text>
        </View>
        <View style={[sharedStyles.badge, { backgroundColor: paymentColors.bg }]}>
          <Text style={[sharedStyles.badgeText, { color: paymentColors.text }]}>
            {(ord.payment_status || 'unpaid').replace('_', ' ')}
          </Text>
        </View>
      </View>

      {/* Items */}
      {ord.items?.map((it, i) => (
        <View key={i} style={styles.orderItemRow}>
          <Text style={{ flex: 1, fontSize: 13, color: colors.textPrimary, fontWeight: '600' }}>
            {it.product_name}
          </Text>
          <Text style={sharedStyles.smallText}>{it.quantity} {it.unit}</Text>
          <Text style={[sharedStyles.smallText, { marginLeft: 8 }]}>
            ₹{((it.price_at_order || 0) * (it.quantity || 0)).toFixed(2)}
          </Text>
        </View>
      ))}

      <View style={[sharedStyles.divider, { marginTop: 8 }]} />
      <View style={{ flexDirection: 'row', justifyContent: 'space-between' }}>
        <Text style={{ fontSize: 14, fontWeight: '800' }}>Total</Text>
        <Text style={{ fontSize: 14, fontWeight: '900', color: colors.primary }}>
          ₹{ord.total_amount?.toFixed(2)}
        </Text>
      </View>

      {/* Payment buttons */}
      {ord.payment_status !== 'paid' && ord.status !== 'rejected' && ord.status !== 'deleted' && (
        <View style={{ marginTop: 12 }}>
          {ord.payment_status === 'cash_pending' || ord.payment_method === 'cash' ? (
            <View style={sharedStyles.warningBox}>
              <Text style={sharedStyles.warningText}>
                💵 Cash payment selected. Pay ₹{ord.total_amount?.toFixed(2)} at the shop.
              </Text>
            </View>
          ) : (
            <View style={{ gap: 8 }}>
              <TouchableOpacity style={[sharedStyles.btnPrimary, { backgroundColor: colors.secondary, marginBottom: 0 }]} onPress={onPayRazorpay}>
                <Text style={sharedStyles.btnPrimaryText}>Pay Online (Razorpay QR)</Text>
              </TouchableOpacity>
              <TouchableOpacity style={sharedStyles.btnSecondary} onPress={onPayCash}>
                <Text style={sharedStyles.btnSecondaryText}>Pay Cash at Shop</Text>
              </TouchableOpacity>
            </View>
          )}

          {/* QR Box */}
          {showPayment && paymentDetails && (
            <View style={styles.qrBox}>
              <Text style={{ fontSize: 13, fontWeight: '700', marginBottom: 4 }}>📱 Scan QR to Pay</Text>
              <Text style={{ fontSize: 17, fontWeight: '900', color: colors.primary, marginBottom: 8 }}>
                ₹{paymentDetails.amount}
              </Text>
              <Image
                source={{ uri: `https://api.qrserver.com/v1/create-qr-code/?size=160x160&data=${encodeURIComponent(paymentDetails.upi_uri)}` }}
                style={{ width: 160, height: 160, borderRadius: 8, borderWidth: 1, borderColor: colors.surfaceBorder }}
              />
              <Text style={[sharedStyles.smallText, { marginTop: 8, fontFamily: Platform.OS === 'ios' ? 'Courier' : 'monospace' }]}>
                Razorpay ID: {paymentDetails.razorpay_order_id}
              </Text>
              <TouchableOpacity
                style={[sharedStyles.btnPrimary, { marginTop: 12, marginBottom: 0 }]}
                onPress={onSimulatePayment}
                disabled={loading}
              >
                {loading
                  ? <ActivityIndicator color="#fff" />
                  : <Text style={sharedStyles.btnPrimaryText}>Simulate Payment Success (Demo)</Text>}
              </TouchableOpacity>
            </View>
          )}
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  logoutBtn: {
    padding: 8,
  },
  shopBar: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.surface,
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: colors.surfaceBorder,
    gap: 8,
  },
  shopBarText: {
    flex: 1,
    fontSize: 14,
    fontWeight: '600',
    color: colors.textPrimary,
  },
  orderItemRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 8,
    gap: 8,
    borderBottomWidth: 1,
    borderBottomColor: colors.surfaceBorder,
  },
  orderItemName: {
    fontSize: 13,
    fontWeight: '700',
    color: colors.textPrimary,
  },
  qtyControls: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  qtyBtn: {
    width: 28,
    height: 28,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: colors.surfaceBorder,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.surfaceLight,
  },
  qtyBtnText: {
    fontSize: 16,
    fontWeight: '700',
    color: colors.textPrimary,
  },
  qtyValue: {
    fontSize: 12,
    fontWeight: '600',
    color: colors.textPrimary,
    minWidth: 50,
    textAlign: 'center',
  },
  addFromCatalogBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    borderWidth: 1,
    borderColor: colors.primary,
    borderRadius: 6,
    paddingHorizontal: 10,
    paddingVertical: 5,
  },
  addFromCatalogText: {
    fontSize: 12,
    color: colors.primary,
    fontWeight: '600',
  },
  inputArea: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    backgroundColor: colors.surface,
    borderTopWidth: 1,
    borderTopColor: colors.surfaceBorder,
    paddingHorizontal: 12,
    paddingVertical: 10,
    gap: 8,
  },
  iconBtn: {
    padding: 8,
  },
  chatInput: {
    flex: 1,
    backgroundColor: colors.surfaceLight,
    borderWidth: 1,
    borderColor: colors.surfaceBorder,
    borderRadius: radius.lg,
    paddingHorizontal: 16,
    paddingVertical: 10,
    fontSize: 14,
    maxHeight: 100,
    color: colors.textPrimary,
  },
  sendBtn: {
    backgroundColor: colors.primary,
    width: 40,
    height: 40,
    borderRadius: 20,
    alignItems: 'center',
    justifyContent: 'center',
  },
  // Modals
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.5)',
    justifyContent: 'flex-end',
  },
  modalSheet: {
    backgroundColor: colors.surface,
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    paddingBottom: 32,
    maxHeight: '70%',
  },
  modalHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: 20,
    borderBottomWidth: 1,
    borderBottomColor: colors.surfaceBorder,
  },
  modalTitle: {
    fontSize: 17,
    fontWeight: '700',
    color: colors.textPrimary,
  },
  modalItem: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 20,
    paddingVertical: 14,
    gap: 12,
  },
  modalItemText: {
    flex: 1,
    fontSize: 15,
    color: colors.textPrimary,
    fontWeight: '600',
  },
  // QR
  qrBox: {
    backgroundColor: colors.surfaceLight,
    borderRadius: radius.md,
    padding: 16,
    marginTop: 12,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: colors.surfaceBorder,
  },
});
