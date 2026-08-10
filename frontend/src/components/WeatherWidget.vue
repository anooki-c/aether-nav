<script setup>
import { ref, onMounted, watch, nextTick } from 'vue'
import { store, setWeatherCity } from '../store'

// WMO 天气代码 → 文案 + Material Symbols 图标
const WMO = {
  0: { t: '晴', i: 'sunny' },
  1: { t: '晴间多云', i: 'sunny' },
  2: { t: '多云', i: 'partly_cloudy_day' },
  3: { t: '阴', i: 'cloud' },
  45: { t: '雾', i: 'foggy' },
  48: { t: '雾凇', i: 'foggy' },
  51: { t: '小毛毛雨', i: 'rainy' },
  53: { t: '毛毛雨', i: 'rainy' },
  55: { t: '大毛毛雨', i: 'rainy' },
  56: { t: '冻毛毛雨', i: 'rainy' },
  57: { t: '强冻毛毛雨', i: 'rainy' },
  61: { t: '小雨', i: 'rainy' },
  63: { t: '中雨', i: 'rainy' },
  65: { t: '大雨', i: 'rainy' },
  66: { t: '冻雨', i: 'rainy' },
  67: { t: '强冻雨', i: 'rainy' },
  71: { t: '小雪', i: 'ac_unit' },
  73: { t: '中雪', i: 'ac_unit' },
  75: { t: '大雪', i: 'ac_unit' },
  77: { t: '雪粒', i: 'ac_unit' },
  80: { t: '阵雨', i: 'rainy' },
  81: { t: '强阵雨', i: 'rainy' },
  82: { t: '暴雨', i: 'rainy' },
  85: { t: '阵雪', i: 'ac_unit' },
  86: { t: '强阵雪', i: 'ac_unit' },
  95: { t: '雷雨', i: 'thunderstorm' },
  96: { t: '雷雨伴冰雹', i: 'thunderstorm' },
  99: { t: '强雷雨伴冰雹', i: 'thunderstorm' },
}

const loading = ref(true)
const error = ref('')
const temp = ref(null)
const code = ref(null)
const cityName = ref('')
const editing = ref(false)
const cityInput = ref('')
const inputRef = ref(null)

const meta = () => WMO[code.value] || { t: '未知', i: 'help' }

async function fetchWeather() {
  loading.value = true
  error.value = ''
  try {
    const city = store.weatherCity
    const geoRes = await fetch(
      `https://geocoding-api.open-meteo.com/v1/search?name=${encodeURIComponent(city)}&count=1&language=zh&format=json`
    )
    const geo = await geoRes.json()
    const loc = geo.results && geo.results[0]
    if (!loc) {
      error.value = '城市未找到'
      loading.value = false
      return
    }
    const adm = loc.admin1 && loc.admin1 !== loc.name && !loc.admin1.includes(loc.name) ? `·${loc.admin1}` : ''
    cityName.value = loc.name + adm
    const wRes = await fetch(
      `https://api.open-meteo.com/v1/forecast?latitude=${loc.latitude}&longitude=${loc.longitude}&current=temperature_2m,weather_code&timezone=auto`
    )
    const w = await wRes.json()
    if (!w.current) {
      error.value = '天气获取失败'
      loading.value = false
      return
    }
    temp.value = Math.round(w.current.temperature_2m)
    code.value = w.current.weather_code
  } catch (e) {
    error.value = '天气获取失败'
  } finally {
    loading.value = false
  }
}

function startEdit() {
  cityInput.value = store.weatherCity
  editing.value = true
  nextTick(() => inputRef.value && inputRef.value.focus())
}
function commitEdit() {
  const c = cityInput.value.trim()
  if (c) setWeatherCity(c)
  editing.value = false
  fetchWeather()
}

onMounted(fetchWeather)
watch(() => store.weatherCity, fetchWeather)
</script>

<template>
  <div
    class="flex items-center gap-2 h-10 px-3 rounded-full bg-surface-container hover:bg-surface-variant transition-colors text-on-surface select-none"
    :title="error || (cityName ? cityName + ' 天气' : '天气')"
  >
    <!-- 编辑态：输入城市（输入元素每次 v-if 新建，挂载即播放上浮淡入） -->
    <input
      v-if="editing"
      ref="inputRef"
      v-model="cityInput"
      class="w-20 bg-transparent outline-none font-body-sm text-body-sm text-on-surface border-b border-outline-variant wfade-in"
      placeholder="城市"
      @keyup.enter="commitEdit"
      @blur="commitEdit"
    />
    <template v-else>
      <span v-if="loading" class="material-symbols-outlined text-[18px] text-on-surface-variant animate-spin">progress_activity</span>
      <span v-else-if="error" class="material-symbols-outlined text-[18px] text-error">cloud_off</span>
      <span v-else class="material-symbols-outlined text-[18px] text-brand">{{ meta().i }}</span>

      <button
        v-if="!loading && !error"
        class="font-body-sm text-body-sm text-on-surface leading-none whitespace-nowrap active:scale-95 transition-transform"
        @click="startEdit"
        :title="'点击修改城市：' + cityName"
      >
        {{ temp }}° {{ meta().t }}
      </button>
      <button
        v-else-if="error"
        class="font-body-sm text-body-sm text-error whitespace-nowrap"
        @click="startEdit"
      >
        重试
      </button>
      <span
        v-if="!loading && !error && cityName"
        class="font-label-sm text-label-sm text-on-surface-variant whitespace-nowrap hidden sm:inline"
      >{{ cityName }}</span>
    </template>
  </div>
</template>

<style scoped>
/* 编辑态输入框：挂载即轻微上浮淡入，避免瞬替 */
.wfade-in {
  animation: wfadeIn 180ms cubic-bezier(0.23, 1, 0.32, 1) both;
}
@keyframes wfadeIn {
  from { opacity: 0; transform: translateY(2px); }
  to { opacity: 1; transform: translateY(0); }
}
</style>
