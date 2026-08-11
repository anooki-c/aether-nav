<script setup>
import { ref } from 'vue'

const props = defineProps({
  modelValue: { type: String, default: '' },
  id: { type: String, default: '' },
  placeholder: { type: String, default: '' },
  // 前导 Material Symbols 图标名（如 'lock'），为空则不显示
  icon: { type: String, default: '' },
  // 容器/输入框的其余样式类（左右内边距由组件统一处理，这里不要再传 pl-/pr-）
  inputClass: { type: String, default: '' },
  autocomplete: { type: String, default: 'current-password' },
  disabled: { type: Boolean, default: false },
})
const emit = defineEmits(['update:modelValue', 'enter'])

const show = ref(false)
function onInput(e) {
  emit('update:modelValue', e.target.value)
}
</script>

<template>
  <div class="relative">
    <span
      v-if="icon"
      class="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-outline text-[20px] pointer-events-none"
    >{{ icon }}</span>
    <input
      :id="id"
      :value="modelValue"
      :type="show ? 'text' : 'password'"
      :placeholder="placeholder"
      :autocomplete="autocomplete"
      :disabled="disabled"
      :class="[
        icon ? 'pl-10' : 'pl-4',
        'pr-11',
        inputClass,
      ]"
      @input="onInput"
      @keyup.enter="$emit('enter')"
    />
    <button
      type="button"
      class="absolute right-3 top-1/2 -translate-y-1/2 text-outline hover:text-primary transition-colors focus:outline-none"
      :title="show ? '隐藏密码' : '显示密码'"
      tabindex="-1"
      @click="show = !show"
    >
      <span class="material-symbols-outlined text-[20px]">{{ show ? 'visibility' : 'visibility_off' }}</span>
    </button>
  </div>
</template>
