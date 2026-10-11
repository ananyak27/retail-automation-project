import React, { useState } from 'react';
import {
  View, Text, TouchableOpacity, ScrollView,
  StyleSheet, ActivityIndicator, Alert, Dimensions,
} from 'react-native';
import { Feather } from '@expo/vector-icons';
import { LineChart } from 'react-native-chart-kit';

import { colors, sharedStyles, radius } from '../../styles/theme';
import { BACKEND_URL } from '../../firebaseConfig';

const { width: SCREEN_WIDTH } = Dimensions.get('window');

const PERIODS = [
  { label: '7 Days', value: 7 },
  { label: '14 Days', value: 14 },
  { label: '30 Days', value: 30 },
  { label: '60 Days', value: 60 },
];

export default function ForecastTab({ session, shop, products }) {
  const [selectedProduct, setSelectedProduct] = useState(null);
  const [period, setPeriod] = useState(7);
  const [forecastData, setForecastData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [showProductPicker, setShowProductPicker] = useState(false);

  const filteredProducts = products.filter(p =>
    p.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const runForecast = async () => {
    if (!selectedProduct || !shop) return;
    setLoading(true);
    setForecastData(null);
    try {
      const res = await fetch(
        `${BACKEND_URL}/api/forecast/?product_id=${selectedProduct.id}&shop_id=${shop.id}&days=${period}`,
        { headers: { 'Authorization': `Bearer ${session.access_token}` } }
      );
      if (res.ok) {
        const data = await res.json();
        setForecastData(data);
      } else {
        Alert.alert('Forecast Error', 'Not enough historical data to generate a forecast.');
      }
    } catch (e) {
      Alert.alert('Error', e.message);
    } finally {
      setLoading(false);
    }
  };

  // Prepare chart data
  const chartData = forecastData ? (() => {
    const labels = forecastData.dates?.slice(0, period).map((d, i) => {
      const date = new Date(d);
      return `${date.getDate()}/${date.getMonth() + 1}`;
    }) || [];
    const yhat = forecastData.yhat?.slice(0, period).map(v => Math.max(0, Math.round(v))) || [];
    const yhat_lower = forecastData.yhat_lower?.slice(0, period).map(v => Math.max(0, Math.round(v))) || [];
    const yhat_upper = forecastData.yhat_upper?.slice(0, period).map(v => Math.max(0, Math.round(v))) || [];

    // Downsample labels for readability
    const step = Math.max(1, Math.floor(labels.length / 6));
    const sampledLabels = labels.filter((_, i) => i % step === 0 || i === labels.length - 1);
    const sampledYhat = yhat.filter((_, i) => i % step === 0 || i === labels.length - 1);

    return { sampledLabels, sampledYhat, yhat, yhat_lower, yhat_upper };
  })() : null;

  return (
    <View style={sharedStyles.screen}>
      <View style={sharedStyles.header}>
        <View style={{ flex: 1 }}>
          <Text style={sharedStyles.headerTitle}>📈 Demand Forecast</Text>
          <Text style={sharedStyles.headerSubtitle}>Powered by Meta Prophet AI</Text>
        </View>
      </View>

      <ScrollView contentContainerStyle={{ padding: 16 }}>

        {/* Product selector */}
        <View style={sharedStyles.card}>
          <Text style={sharedStyles.label}>Select Product</Text>
          <TouchableOpacity
            style={styles.productSelector}
            onPress={() => setShowProductPicker(!showProductPicker)}
          >
            <Feather name="box" size={16} color={colors.primary} />
            <Text style={{ flex: 1, fontSize: 14, color: selectedProduct ? colors.textPrimary : colors.textMuted, marginLeft: 8 }}>
              {selectedProduct ? selectedProduct.name : 'Choose a product...'}
            </Text>
            <Feather name={showProductPicker ? 'chevron-up' : 'chevron-down'} size={16} color={colors.textSecondary} />
          </TouchableOpacity>

          {showProductPicker && (
            <View style={styles.productDropdown}>
              {filteredProducts.map(p => (
                <TouchableOpacity
                  key={p.id}
                  style={styles.productOption}
                  onPress={() => {
                    setSelectedProduct(p);
                    setShowProductPicker(false);
                    setForecastData(null);
                  }}
                >
                  <Text style={{ fontSize: 14, color: colors.textPrimary }}>{p.name}</Text>
                  {selectedProduct?.id === p.id && (
                    <Feather name="check" size={16} color={colors.secondary} />
                  )}
                </TouchableOpacity>
              ))}
            </View>
          )}
        </View>

        {/* Period selector */}
        <View style={sharedStyles.card}>
          <Text style={sharedStyles.label}>Forecast Period</Text>
          <View style={{ flexDirection: 'row', gap: 8, flexWrap: 'wrap' }}>
            {PERIODS.map(p => (
              <TouchableOpacity
                key={p.value}
                style={[styles.periodChip, period === p.value && styles.periodChipActive]}
                onPress={() => setPeriod(p.value)}
              >
                <Text style={[styles.periodChipText, period === p.value && styles.periodChipTextActive]}>
                  {p.label}
                </Text>
              </TouchableOpacity>
            ))}
          </View>
        </View>

        {/* Run button */}
        <TouchableOpacity
          style={[sharedStyles.btnPrimary, (!selectedProduct || loading) && sharedStyles.btnDisabled]}
          onPress={runForecast}
          disabled={!selectedProduct || loading}
        >
          {loading
            ? <ActivityIndicator color="#fff" />
            : <Text style={sharedStyles.btnPrimaryText}>▶ Run Forecast</Text>}
        </TouchableOpacity>

        {/* Results */}
        {forecastData && chartData && (
          <View style={{ marginTop: 8 }}>
            {/* Summary cards */}
            <View style={{ flexDirection: 'row', gap: 12, marginBottom: 12 }}>
              <View style={[sharedStyles.card, { flex: 1, alignItems: 'center' }]}>
                <Text style={sharedStyles.smallText}>Total Demand</Text>
                <Text style={{ fontSize: 22, fontWeight: '900', color: colors.primary }}>
                  {chartData.yhat.reduce((a, b) => a + b, 0).toFixed(0)}
                </Text>
                <Text style={sharedStyles.smallText}>{selectedProduct.unit}</Text>
              </View>
              <View style={[sharedStyles.card, { flex: 1, alignItems: 'center' }]}>
                <Text style={sharedStyles.smallText}>Daily Avg</Text>
                <Text style={{ fontSize: 22, fontWeight: '900', color: colors.secondary }}>
                  {(chartData.yhat.reduce((a, b) => a + b, 0) / chartData.yhat.length).toFixed(1)}
                </Text>
                <Text style={sharedStyles.smallText}>{selectedProduct.unit}/day</Text>
              </View>
              <View style={[sharedStyles.card, { flex: 1, alignItems: 'center' }]}>
                <Text style={sharedStyles.smallText}>Peak Day</Text>
                <Text style={{ fontSize: 22, fontWeight: '900', color: colors.warning }}>
                  {Math.max(...chartData.yhat).toFixed(0)}
                </Text>
                <Text style={sharedStyles.smallText}>{selectedProduct.unit}</Text>
              </View>
            </View>

            {/* Line Chart */}
            <View style={sharedStyles.card}>
              <Text style={[sharedStyles.sectionTitle, { marginBottom: 12 }]}>
                📊 {selectedProduct.name} — {period}-Day Forecast
              </Text>
              <LineChart
                data={{
                  labels: chartData.sampledLabels,
                  datasets: [{ data: chartData.sampledYhat, color: () => colors.primary, strokeWidth: 2 }],
                }}
                width={SCREEN_WIDTH - 64}
                height={200}
                chartConfig={{
                  backgroundColor: colors.surface,
                  backgroundGradientFrom: colors.surface,
                  backgroundGradientTo: colors.surface,
                  decimalPlaces: 0,
                  color: (opacity = 1) => `rgba(99, 102, 241, ${opacity})`,
                  labelColor: () => colors.textSecondary,
                  propsForDots: { r: '4', strokeWidth: '2', stroke: colors.primary },
                }}
                bezier
                style={{ borderRadius: radius.sm, marginHorizontal: -4 }}
              />
              <Text style={[sharedStyles.smallText, { textAlign: 'center', marginTop: 8 }]}>
                Forecast generated using Meta Prophet AI model
              </Text>
            </View>

            {/* Restock recommendation */}
            <View style={[sharedStyles.card, { borderColor: colors.warning, borderWidth: 1.5 }]}>
              <Text style={{ fontWeight: '700', fontSize: 15, marginBottom: 8 }}>📦 Restock Recommendation</Text>
              <Text style={sharedStyles.bodyText}>
                Based on the forecast, you should stock at least{' '}
                <Text style={{ fontWeight: '900', color: colors.primary }}>
                  {Math.ceil(chartData.yhat_upper.reduce((a, b) => a + b, 0))} {selectedProduct.unit}
                </Text>{' '}
                for the next {period} days to meet maximum expected demand.
              </Text>
              <Text style={[sharedStyles.smallText, { marginTop: 6 }]}>
                Current stock: {selectedProduct.stock} {selectedProduct.unit}
              </Text>
            </View>
          </View>
        )}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  productSelector: {
    flexDirection: 'row',
    alignItems: 'center',
    borderWidth: 1,
    borderColor: colors.surfaceBorder,
    borderRadius: radius.sm,
    padding: 12,
    backgroundColor: colors.surfaceLight,
  },
  productDropdown: {
    borderWidth: 1,
    borderColor: colors.surfaceBorder,
    borderRadius: radius.sm,
    marginTop: 8,
    backgroundColor: colors.surface,
    maxHeight: 220,
    overflow: 'hidden',
  },
  productOption: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: 12,
    borderBottomWidth: 1,
    borderBottomColor: colors.surfaceBorder,
  },
  periodChip: {
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 20,
    borderWidth: 1,
    borderColor: colors.surfaceBorder,
    backgroundColor: colors.surfaceLight,
  },
  periodChipActive: {
    backgroundColor: colors.primary,
    borderColor: colors.primary,
  },
  periodChipText: {
    fontSize: 13,
    fontWeight: '600',
    color: colors.textSecondary,
  },
  periodChipTextActive: {
    color: '#fff',
  },
});
