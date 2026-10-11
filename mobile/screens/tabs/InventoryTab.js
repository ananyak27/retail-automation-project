import React, { useState } from 'react';
import {
  View, Text, FlatList, TouchableOpacity, TextInput,
  StyleSheet, ActivityIndicator, Alert, Modal, ScrollView,
} from 'react-native';
import { Feather } from '@expo/vector-icons';

import { colors, sharedStyles, radius } from '../../styles/theme';
import { BACKEND_URL } from '../../firebaseConfig';

const UNITS = ['kg', 'g', 'litre', 'ml', 'piece', 'dozen', 'pack', 'box'];

export default function InventoryTab({ session, shop, products, onRefreshProducts }) {
  const [mode, setMode] = useState('list'); // 'list' | 'add' | 'edit'
  const [selectedProduct, setSelectedProduct] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [loading, setLoading] = useState(false);

  // Form fields
  const [name, setName] = useState('');
  const [price, setPrice] = useState('');
  const [stock, setStock] = useState('');
  const [unit, setUnit] = useState('kg');
  const [threshold, setThreshold] = useState('10');

  const filteredProducts = products.filter(p =>
    p.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const openAddForm = () => {
    setSelectedProduct(null);
    setName(''); setPrice(''); setStock(''); setUnit('kg'); setThreshold('10');
    setMode('add');
  };

  const openEditForm = (product) => {
    setSelectedProduct(product);
    setName(product.name);
    setPrice(String(product.price));
    setStock(String(product.stock));
    setUnit(product.unit || 'kg');
    setThreshold(String(product.low_stock_threshold || 10));
    setMode('edit');
  };

  const handleSave = async () => {
    if (!name.trim()) { Alert.alert('Error', 'Product name is required.'); return; }
    if (!price || isNaN(parseFloat(price))) { Alert.alert('Error', 'Enter a valid price.'); return; }
    if (!stock || isNaN(parseFloat(stock))) { Alert.alert('Error', 'Enter a valid stock quantity.'); return; }

    setLoading(true);
    const payload = {
      name: name.trim(),
      price: parseFloat(price),
      stock: parseFloat(stock),
      unit,
      low_stock_threshold: parseFloat(threshold) || 10,
      shop_id: shop.id,
    };

    try {
      let res;
      if (mode === 'add') {
        res = await fetch(`${BACKEND_URL}/api/products/`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${session.access_token}`,
          },
          body: JSON.stringify(payload),
        });
      } else {
        res = await fetch(`${BACKEND_URL}/api/products/${selectedProduct.id}`, {
          method: 'PUT',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${session.access_token}`,
          },
          body: JSON.stringify(payload),
        });
      }

      if (res.ok) {
        Alert.alert('Success', mode === 'add' ? 'Product added!' : 'Product updated!');
        setMode('list');
        onRefreshProducts();
      } else {
        const detail = await res.json();
        Alert.alert('Error', detail.detail || 'Operation failed.');
      }
    } catch (e) {
      Alert.alert('Error', e.message);
    } finally {
      setLoading(false);
    }
  };

  const handleRestock = async (product, qty) => {
    const quantity = parseFloat(qty);
    if (!quantity || quantity <= 0) return;
    try {
      await fetch(`${BACKEND_URL}/api/products/${product.id}/restock`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${session.access_token}`,
        },
        body: JSON.stringify({ quantity }),
      });
      onRefreshProducts();
    } catch (e) {
      Alert.alert('Error', e.message);
    }
  };

  const handleDelete = (product) => {
    Alert.alert('Delete Product', `Delete "${product.name}"?`, [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Delete',
        style: 'destructive',
        onPress: async () => {
          try {
            await fetch(`${BACKEND_URL}/api/products/${product.id}`, {
              method: 'DELETE',
              headers: { 'Authorization': `Bearer ${session.access_token}` },
            });
            onRefreshProducts();
          } catch (e) {
            Alert.alert('Error', e.message);
          }
        },
      },
    ]);
  };

  if (mode !== 'list') {
    // ── Add / Edit Form ────────────────────────────────────────────────────────
    return (
      <View style={sharedStyles.screen}>
        <View style={sharedStyles.header}>
          <TouchableOpacity onPress={() => setMode('list')} style={{ padding: 4 }}>
            <Feather name="arrow-left" size={22} color="#fff" />
          </TouchableOpacity>
          <Text style={[sharedStyles.headerTitle, { marginLeft: 12 }]}>
            {mode === 'add' ? '➕ Add Product' : '✏️ Edit Product'}
          </Text>
        </View>
        <ScrollView contentContainerStyle={{ padding: 20 }}>
          <Text style={sharedStyles.label}>Product Name *</Text>
          <TextInput style={sharedStyles.input} placeholder="e.g. Basmati Rice" value={name} onChangeText={setName} />

          <View style={{ flexDirection: 'row', gap: 12 }}>
            <View style={{ flex: 1 }}>
              <Text style={sharedStyles.label}>Price (₹) *</Text>
              <TextInput style={sharedStyles.input} placeholder="0.00" value={price} onChangeText={setPrice} keyboardType="decimal-pad" />
            </View>
            <View style={{ flex: 1 }}>
              <Text style={sharedStyles.label}>Stock *</Text>
              <TextInput style={sharedStyles.input} placeholder="0" value={stock} onChangeText={setStock} keyboardType="decimal-pad" />
            </View>
          </View>

          <Text style={sharedStyles.label}>Unit</Text>
          <ScrollView horizontal showsHorizontalScrollIndicator={false}
            contentContainerStyle={{ gap: 8, marginBottom: 14 }}
          >
            {UNITS.map(u => (
              <TouchableOpacity
                key={u}
                style={[styles.unitChip, unit === u && styles.unitChipActive]}
                onPress={() => setUnit(u)}
              >
                <Text style={[styles.unitChipText, unit === u && styles.unitChipTextActive]}>{u}</Text>
              </TouchableOpacity>
            ))}
          </ScrollView>

          <Text style={sharedStyles.label}>Low Stock Threshold</Text>
          <TextInput style={sharedStyles.input} placeholder="10" value={threshold} onChangeText={setThreshold} keyboardType="decimal-pad" />

          <TouchableOpacity
            style={[sharedStyles.btnPrimary, loading && sharedStyles.btnDisabled]}
            onPress={handleSave}
            disabled={loading}
          >
            {loading ? <ActivityIndicator color="#fff" /> : <Text style={sharedStyles.btnPrimaryText}>Save Product</Text>}
          </TouchableOpacity>
          <TouchableOpacity style={sharedStyles.btnSecondary} onPress={() => setMode('list')}>
            <Text style={sharedStyles.btnSecondaryText}>Cancel</Text>
          </TouchableOpacity>
        </ScrollView>
      </View>
    );
  }

  // ── Product List ─────────────────────────────────────────────────────────────
  return (
    <View style={sharedStyles.screen}>
      <View style={sharedStyles.header}>
        <View style={{ flex: 1 }}>
          <Text style={sharedStyles.headerTitle}>📦 Inventory</Text>
          <Text style={sharedStyles.headerSubtitle}>{products.length} products</Text>
        </View>
        <TouchableOpacity onPress={openAddForm} style={styles.addBtn}>
          <Feather name="plus" size={18} color="#fff" />
          <Text style={{ color: '#fff', fontWeight: '700', fontSize: 13 }}>Add</Text>
        </TouchableOpacity>
        <TouchableOpacity onPress={onRefreshProducts} style={{ padding: 8, marginLeft: 4 }}>
          <Feather name="refresh-cw" size={18} color="rgba(255,255,255,0.8)" />
        </TouchableOpacity>
      </View>

      {/* Search */}
      <View style={styles.searchBar}>
        <Feather name="search" size={16} color={colors.textSecondary} />
        <TextInput
          style={{ flex: 1, marginLeft: 8, fontSize: 14, color: colors.textPrimary }}
          placeholder="Search products..."
          value={searchQuery}
          onChangeText={setSearchQuery}
        />
      </View>

      {filteredProducts.length === 0 ? (
        <View style={sharedStyles.emptyContainer}>
          <Feather name="package" size={48} color={colors.textMuted} />
          <Text style={sharedStyles.emptyText}>
            {searchQuery ? 'No products match your search.' : 'No products yet. Tap Add to create one.'}
          </Text>
        </View>
      ) : (
        <FlatList
          data={filteredProducts}
          keyExtractor={item => String(item.id)}
          contentContainerStyle={{ padding: 16 }}
          renderItem={({ item: p }) => {
            const isLow = p.stock <= (p.low_stock_threshold || 10);
            return (
              <View style={[sharedStyles.card, isLow && { borderColor: colors.error, borderWidth: 1.5 }]}>
                <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                  <View style={{ flex: 1 }}>
                    <Text style={{ fontWeight: '700', fontSize: 15, color: colors.textPrimary }}>
                      {p.name}
                    </Text>
                    <Text style={sharedStyles.smallText}>₹{p.price}/{p.unit}</Text>
                  </View>
                  <View style={{ flexDirection: 'row', gap: 8 }}>
                    <TouchableOpacity onPress={() => openEditForm(p)}>
                      <Feather name="edit-2" size={18} color={colors.primary} />
                    </TouchableOpacity>
                    <TouchableOpacity onPress={() => handleDelete(p)}>
                      <Feather name="trash-2" size={18} color={colors.error} />
                    </TouchableOpacity>
                  </View>
                </View>

                <View style={{ flexDirection: 'row', alignItems: 'center', marginTop: 10, gap: 8 }}>
                  <View style={[sharedStyles.badge, {
                    backgroundColor: isLow ? colors.errorLight : colors.secondaryLight,
                  }]}>
                    <Text style={[sharedStyles.badgeText, {
                      color: isLow ? colors.error : colors.secondary,
                    }]}>
                      {isLow ? '⚠️ Low Stock' : '✅ In Stock'}
                    </Text>
                  </View>
                  <Text style={{ fontSize: 13, fontWeight: '700', color: isLow ? colors.error : colors.textPrimary }}>
                    {p.stock} {p.unit}
                  </Text>
                </View>

                {isLow && (
                  <RestockRow
                    product={p}
                    onRestock={(qty) => handleRestock(p, qty)}
                  />
                )}
              </View>
            );
          }}
        />
      )}
    </View>
  );
}

function RestockRow({ product, onRestock }) {
  const [restockQty, setRestockQty] = useState('');
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', marginTop: 10, gap: 8 }}>
      <TextInput
        style={[sharedStyles.input, { flex: 1, marginBottom: 0, paddingVertical: 8 }]}
        placeholder={`Restock qty (${product.unit})`}
        value={restockQty}
        onChangeText={setRestockQty}
        keyboardType="decimal-pad"
      />
      <TouchableOpacity
        style={[sharedStyles.btnPrimary, { paddingVertical: 10, paddingHorizontal: 14, marginBottom: 0 }]}
        onPress={() => { onRestock(restockQty); setRestockQty(''); }}
      >
        <Text style={sharedStyles.btnPrimaryText}>Restock</Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  addBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    backgroundColor: 'rgba(255,255,255,0.15)',
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 6,
  },
  searchBar: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderBottomWidth: 1,
    borderBottomColor: colors.surfaceBorder,
    paddingHorizontal: 16,
    paddingVertical: 10,
  },
  unitChip: {
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 20,
    borderWidth: 1,
    borderColor: colors.surfaceBorder,
    backgroundColor: colors.surfaceLight,
  },
  unitChipActive: {
    backgroundColor: colors.primary,
    borderColor: colors.primary,
  },
  unitChipText: {
    fontSize: 12,
    color: colors.textSecondary,
    fontWeight: '600',
  },
  unitChipTextActive: {
    color: '#fff',
  },
});
