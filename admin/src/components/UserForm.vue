<template>
  <form @submit.prevent="handleSubmit" class="user-form">
    <!-- User ID (Read-only, shown only in edit mode) -->
    <div v-if="isEditMode" class="form-group">
      <label for="userId">ユーザーID</label>
      <input id="userId" :value="props.user.id" type="text" disabled />
    </div>

    <!-- Name (Required, Read-only in Edit Mode) -->
    <div class="form-group">
      <label for="name" class="required">氏名</label>
      <input
        id="name"
        v-model="formData.name"
        type="text"
        placeholder="山田 太郎"
        required
        :disabled="isEditMode"
        :class="{ error: errors.name }"
      />
      <span v-if="errors.name" class="error-message">{{ errors.name }}</span>
    </div>

    <!-- Nickname (Optional) -->
    <div class="form-group">
      <label for="nickname">呼び方</label>
      <input id="nickname" v-model="formData.nickname" type="text" placeholder="太郎さん" />
    </div>

    <!-- Room Number (Optional) -->
    <div class="form-group">
      <label for="roomNumber">部屋番号</label>
      <input id="roomNumber" v-model="formData.roomNumber" type="text" placeholder="101" />
    </div>

    <!-- Device ID (Required, Read-only in Edit Mode) -->
    <div class="form-group">
      <label for="deviceId" class="required">デバイスID</label>
      <input
        id="deviceId"
        v-model="formData.deviceId"
        type="text"
        placeholder="devicenumber99"
        required
        :disabled="isEditMode"
        :class="{ error: errors.deviceId }"
      />
      <span v-if="errors.deviceId" class="error-message">{{ errors.deviceId }}</span>
    </div>

    <!-- Notes (Optional) -->
    <div class="form-group">
      <label for="notes">備考</label>
      <textarea
        id="notes"
        v-model="formData.notes"
        rows="3"
        placeholder="特記事項があれば記入"
      ></textarea>
    </div>

    <!-- Action Buttons -->
    <div class="form-actions">
      <button type="button" @click="handleCancel" class="btn-secondary">キャンセル</button>
      <button type="submit" class="btn-primary" :disabled="!isFormValid">
        {{ isEditMode ? '更新' : '登録' }}
      </button>
    </div>
  </form>
</template>

<script setup>
import { reactive, computed, watch } from 'vue'

// Props
const props = defineProps({
  user: {
    type: Object,
    default: null,
  },
})

// Emits
const emit = defineEmits(['submit', 'cancel'])

// Check if in edit mode
const isEditMode = computed(() => props.user !== null)

// Form data
const formData = reactive({
  name: '',
  nickname: '',
  roomNumber: '',
  deviceId: '',
  notes: '',
})

// Error state
const errors = reactive({
  name: '',
  deviceId: '',
})

// Populate form when props.user changes (edit mode)
watch(
  () => props.user,
  newUser => {
    if (newUser) {
      formData.name = newUser.name || ''
      formData.nickname = newUser.nickname || ''
      formData.roomNumber = newUser.roomNumber || ''
      formData.deviceId = newUser.deviceId || ''
      formData.notes = newUser.notes || ''
    } else {
      // Reset form for create mode
      resetForm()
    }
  },
  { immediate: true }
)

// Form validation check
const isFormValid = computed(() => {
  return formData.name.trim() !== '' && formData.deviceId !== ''
})

// Validate form fields
function validateForm() {
  errors.name = ''
  errors.deviceId = ''

  if (!formData.name.trim()) {
    errors.name = '氏名は必須です'
  }

  if (!formData.deviceId) {
    errors.deviceId = 'デバイスは必須です'
  }

  return !errors.name && !errors.deviceId
}

// Handle form submission
function handleSubmit() {
  if (!validateForm()) {
    return
  }

  // Convert empty strings to null for optional fields
  const userData = {
    name: formData.name.trim(),
    nickname: formData.nickname.trim() || null,
    roomNumber: formData.roomNumber.trim() || null,
    deviceId: formData.deviceId,
    notes: formData.notes.trim() || null,
  }

  emit('submit', userData)
}

// Handle cancel action
function handleCancel() {
  resetForm()
  emit('cancel')
}

// Reset form to initial state
function resetForm() {
  formData.name = ''
  formData.nickname = ''
  formData.roomNumber = ''
  formData.deviceId = ''
  formData.notes = ''
  errors.name = ''
  errors.deviceId = ''
}
</script>

<style scoped>
.user-form {
  max-width: 600px;
  margin: 0 auto;
}

.form-group {
  margin-bottom: 1.5rem;
}

label {
  display: block;
  margin-bottom: 0.5rem;
  font-weight: 500;
  color: #374151;
}

label.required::after {
  content: ' *';
  color: #ef4444;
}

input[type='text'],
select,
textarea {
  width: 100%;
  padding: 0.5rem 0.75rem;
  border: 1px solid #d1d5db;
  border-radius: 0.375rem;
  font-size: 1rem;
  transition: border-color 0.15s ease-in-out;
}

input[type='text']:focus,
select:focus,
textarea:focus {
  outline: none;
  border-color: #3b82f6;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}

input.error,
select.error {
  border-color: #ef4444;
}

.error-message {
  display: block;
  margin-top: 0.25rem;
  font-size: 0.875rem;
  color: #ef4444;
}

/* Disabled input styling */
input:disabled,
textarea:disabled {
  background-color: #f3f4f6;
  color: #6b7280;
  cursor: not-allowed;
}

textarea {
  resize: vertical;
  min-height: 80px;
}

.form-actions {
  display: flex;
  justify-content: flex-end;
  gap: 1rem;
  margin-top: 2rem;
}

.btn-primary,
.btn-secondary {
  padding: 0.5rem 1.5rem;
  border: none;
  border-radius: 0.375rem;
  font-size: 1rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s ease-in-out;
}

.btn-primary {
  background-color: #3b82f6;
  color: white;
}

.btn-primary:hover:not(:disabled) {
  background-color: #2563eb;
}

.btn-primary:disabled {
  background-color: #9ca3af;
  cursor: not-allowed;
}

.btn-secondary {
  background-color: #f3f4f6;
  color: #374151;
}

.btn-secondary:hover {
  background-color: #e5e7eb;
}
</style>
