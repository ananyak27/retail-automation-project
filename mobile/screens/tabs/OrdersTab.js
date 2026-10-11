import React, { useState } from 'react';
import {
  View, Text, FlatList, TouchableOpacity, ScrollView,
  StyleSheet, ActivityIndicator, Alert, Modal, TextInput,
} from 'react-native';
import { Feather } from '@expo/vector-icons';

import { colors, sharedStyles, getStatusColors } from '../../styles/theme';
import { BACKEND_URL } from '../../firebaseConfig';
import { formatDateTime } from '../../utils/dateTimeUtils';

export default function OrdersTab({ session, shop, orders, onRefreshOrders }) {
  const [reviewOrder, setReviewOrder] = useState(null);
  const [reviewItems, setReviewItems] = useState([]);
  const [reviewNotes, setReviewNotes] = useState('');
  const [loading, setLoading] = useState(false);
  const [filter, setFilter] = useState('all'); // 'all' | 'pending' | 'approved' | 'rejected'

  const filteredOrders = filter === 'all'
    ? orders
    : orders.filter(o => o.status === filter);

  const openReview = (ord) => {
    setReviewOrder(ord);
    setReviewItems(ord.items?.map(i => ({ ...i })) || []);
    setReviewNotes('');
  };

  const closeReview = () => {
    setReviewOrder(null);
    setReviewItems([]);
    setReviewNotes('');
  };

  const handleUpdateItemQty = (index, delta) => {
    setReviewItems(prev => {
      const updated = [...prev];
      const newQty = Math.max(0.1, (parseFloat(updated[index].quantity) || 0) + delta);
      updated[index] = { ...updated[index], quantity: Math.round(newQty * 10) / 10 };
      return updated;
    });
  };

  const handleApproveOrder = async () => {
    if (!reviewOrder) return;
    setLoading(true);
    try {
      const payload = {
        status: 'approved',
        notes: reviewNotes || null,
        items: reviewItems.map(i => ({
          order_item_id: i.id,
          quantity: i.quantity,
        })),
      };
      const res = await fetch(`${BACKEND_URL}/api/orders/${reviewOrder.id}/review`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${session.access_token}`,
        },
        body: JSON.stringify(payload),
      });
      if (res.ok) {
        Alert.alert('✅ Order Approved', 'The customer has been notified.');
        closeReview();
        onRefreshOrders();
      } else {
        Alert.alert('Error', 'Failed to approve order.');
      }
    } catch (e) {
      Alert.alert('Error', e.message);
    } finally {
      setLoading(false);
    }
  };

  const handleRejectOrder = async () => {
    if (!reviewOrder) return;
    Alert.alert('Reject Order', 'Are you sure you want to reject this order?', [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Reject',
        style: 'destructive',
        onPress: async () => {
          setLoading(true);
          try {
            const res = await fetch(`${BACKEND_URL}/api/orders/${reviewOrder.id}/review`, {
              method: 'POST',
              headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${session.access_token}`,
              },
              body: JSON.stringify({ status: 'rejected', notes: reviewNotes || null }),
            });
            if (res.ok) {
              Alert.alert('Order Rejected', 'The order has been rejected.');
              closeReview();
              onRefreshOrders();
            }
          } catch (e) {
            Alert.alert('Error', e.message);
          } finally {
            setLoading(false);
          }
        },
      },
    ]);
  };

  const handleDeleteOrder = async (ordId) => {
    Alert.alert('Delete Order', 'Delete this order permanently?', [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Delete',
        style: 'destructive',
        onPress: async () => {
          try {
            await fetch(`${BACKEND_URL}/api/orders/${ordId}`, {
              method: 'DELETE',
              headers: { 'Authorization': `Bearer ${session.access_token}` },
            });
            onRefreshOrders();
          } catch (e) {
            Alert.alert('Error', e.message);
          }
        },
      },
    ]);
  };

  return (
    <View style={sharedStyles.screen}>
      {/* Header */}
      <View style={sharedStyles.header}>
        <View style={{ flex: 1 }}>
          <Text style={sharedStyles.headerTitle}>📦 Orders</Text>
          <Text style={sharedStyles.headerSubtitle}>{shop?.name}</Text>
        </View>
        <TouchableOpacity onPress={onRefreshOrders} style={{ padding: 8 }}>
          <Feather name="refresh-cw" size={18} color="rgba(255,255,255,0.8)" />
        </TouchableOpacity>
      </View>

      {/* Filter chips */}
      <ScrollView horizontal showsHorizontalScrollIndicator={false}
        style={{ flexGrow: 0, backgroundColor: colors.surface, borderBottomWidth: 1, borderBottomColor: colors.surfaceBorder }}
        contentContainerStyle={{ paddingHorizontal: 16, paddingVertical: 10, gap: 8 }}
      >
        {['all', 'pending_review', 'approved', 'rejected'].map(f => (
          <TouchableOpacity
            key={f}
            onPress={() => setFilter(f)}
            style={[styles.filterChip, filter === f && styles.filterChipActive]}
          >
            <Text style={[styles.filterChipText, filter === f && styles.filterChipTextActive]}>
              {f === 'all' ? 'All' : f.replace('_', ' ')}
              {f === 'all' && ` (${orders.length})`}
              {f === 'pending_review' && ` (${orders.filter(o => o.status === 'pending_review' || o.status === 'pending').length})`}
            </Text>
          </TouchableOpacity>
        ))}
      </ScrollView>

      {filteredOrders.length === 0 ? (
        <View style={sharedStyles.emptyContainer}>
          <Feather name="inbox" size={48} color={colors.textMuted} />
          <Text style={sharedStyles.emptyText}>No orders found.</Text>
        </View>
      ) : (
        <FlatList
          data={filteredOrders}
          keyExtractor={item => String(item.id)}
          contentContainerStyle={{ padding: 16 }}
          renderItem={({ item: ord }) => {
            const sc = getStatusColors(ord.status);
            const pc = getStatusColors(ord.payment_status);
            const isPending = ord.status === 'pending' || ord.status === 'pending_review';
            return (
              <View style={sharedStyles.card}>
                <View style={{ flexDirection: 'row', justifyContent: 'space-between', marginBottom: 6 }}>
                  <Text style={{ fontWeight: '800', fontSize: 15, color: colors.primary }}>
                    Order #{ord.order_number || ord.id}
                  </Text>
                  <Text style={sharedStyles.smallText}>{formatDateTime(ord.created_at)}</Text>
                </View>
                <Text style={[sharedStyles.smallText, { marginBottom: 8 }]}>
                  Customer: {ord.customer_name || ord.customer_phone}
                </Text>
                <View style={{ flexDirection: 'row', gap: 6, marginBottom: 10 }}>
                  <View style={[sharedStyles.badge, { backgroundColor: sc.bg }]}>
                    <Text style={[sharedStyles.badgeText, { color: sc.text }]}>
                      {(ord.status || 'pending').replace('_', ' ')}
                    </Text>
                  </View>
                  <View style={[sharedStyles.badge, { backgroundColor: pc.bg }]}>
                    <Text style={[sharedStyles.badgeText, { color: pc.text }]}>
                      {(ord.payment_status || 'unpaid').replace('_', ' ')}
                    </Text>
                  </View>
                </View>

                {/* Items preview */}
                {ord.items?.slice(0, 2).map((it, i) => (
                  <Text key={i} style={sharedStyles.smallText}>
                    • {it.product_name} × {it.quantity} {it.unit}
                  </Text>
                ))}
                {ord.items?.length > 2 && (
                  <Text style={[sharedStyles.smallText, { color: colors.primary }]}>
                    +{ord.items.length - 2} more items
                  </Text>
                )}

                <View style={[sharedStyles.divider, { marginTop: 10 }]} />
                <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
                  <Text style={{ fontWeight: '800', color: colors.primary, fontSize: 15 }}>
                    ₹{ord.total_amount?.toFixed(2)}
                  </Text>
                  <View style={{ flexDirection: 'row', gap: 8 }}>
                    {isPending && (
                      <TouchableOpacity
                        style={[sharedStyles.btnPrimary, { paddingVertical: 8, paddingHorizontal: 14, marginBottom: 0 }]}
                        onPress={() => openReview(ord)}
                      >
                        <Text style={[sharedStyles.btnPrimaryText, { fontSize: 13 }]}>Review</Text>
                      </TouchableOpacity>
                    )}
                    <TouchableOpacity
                      onPress={() => handleDeleteOrder(ord.id)}
                      style={{ padding: 8 }}
                    >
                      <Feather name="trash-2" size={18} color={colors.error} />
                    </TouchableOpacity>
                  </View>
                </View>
              </View>
            );
          }}
        />
      )}

      {/* Review Order Modal */}
      <Modal visible={!!reviewOrder} animationType="slide">
        <View style={{ flex: 1, backgroundColor: colors.surfaceLight }}>
          <View style={sharedStyles.header}>
            <Text style={sharedStyles.headerTitle}>Review Order</Text>
            <TouchableOpacity onPress={closeReview}>
              <Feather name="x" size={22} color="#fff" />
            </TouchableOpacity>
          </View>
          <ScrollView contentContainerStyle={{ padding: 16 }}>
            <Text style={[sharedStyles.sectionTitle, { marginBottom: 12 }]}>
              Order #{reviewOrder?.order_number || reviewOrder?.id}
            </Text>

            {reviewItems.map((item, idx) => (
              <View key={idx} style={[sharedStyles.card, { padding: 12 }]}>
                <Text style={{ fontWeight: '700', marginBottom: 6 }}>{item.product_name}</Text>
                <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
                  <TouchableOpacity style={styles.qtyBtn} onPress={() => handleUpdateItemQty(idx, -0.5)}>
                    <Text style={styles.qtyBtnText}>−</Text>
                  </TouchableOpacity>
                  <Text style={{ fontSize: 15, fontWeight: '700', minWidth: 60, textAlign: 'center' }}>
                    {item.quantity} {item.unit}
                  </Text>
                  <TouchableOpacity style={styles.qtyBtn} onPress={() => handleUpdateItemQty(idx, 0.5)}>
                    <Text style={styles.qtyBtnText}>+</Text>
                  </TouchableOpacity>
                  <Text style={[sharedStyles.smallText, { marginLeft: 'auto' }]}>
                    ₹{((item.price_at_order || 0) * item.quantity).toFixed(2)}
                  </Text>
                </View>
              </View>
            ))}

            <View style={sharedStyles.card}>
              <Text style={sharedStyles.label}>Notes to Customer (optional)</Text>
              <TextInput
                style={[sharedStyles.input, { height: 80, textAlignVertical: 'top', marginBottom: 0 }]}
                placeholder="e.g. Some items are out of stock..."
                value={reviewNotes}
                onChangeText={setReviewNotes}
                multiline
              />
            </View>

            <TouchableOpacity
              style={[sharedStyles.btnPrimary, loading && sharedStyles.btnDisabled]}
              onPress={handleApproveOrder}
              disabled={loading}
            >
              {loading ? <ActivityIndicator color="#fff" /> : <Text style={sharedStyles.btnPrimaryText}>✅ Approve Order</Text>}
            </TouchableOpacity>

            <TouchableOpacity
              style={[sharedStyles.btnDanger, loading && sharedStyles.btnDisabled]}
              onPress={handleRejectOrder}
              disabled={loading}
            >
              <Text style={sharedStyles.btnDangerText}>❌ Reject Order</Text>
            </TouchableOpacity>

            <TouchableOpacity style={[sharedStyles.btnSecondary, { marginTop: 4 }]} onPress={closeReview}>
              <Text style={sharedStyles.btnSecondaryText}>Cancel</Text>
            </TouchableOpacity>
          </ScrollView>
        </View>
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  filterChip: {
    paddingHorizontal: 14,
    paddingVertical: 6,
    borderRadius: 20,
    borderWidth: 1,
    borderColor: colors.surfaceBorder,
    backgroundColor: colors.surfaceLight,
  },
  filterChipActive: {
    backgroundColor: colors.primary,
    borderColor: colors.primary,
  },
  filterChipText: {
    fontSize: 12,
    fontWeight: '600',
    color: colors.textSecondary,
    textTransform: 'capitalize',
  },
  filterChipTextActive: {
    color: '#fff',
  },
  qtyBtn: {
    width: 32,
    height: 32,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: colors.surfaceBorder,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.surfaceLight,
  },
  qtyBtnText: {
    fontSize: 18,
    fontWeight: '700',
    color: colors.textPrimary,
  },
});
