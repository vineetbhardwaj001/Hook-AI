// server/routes/authRoutes.js
const express = require('express');
const router = express.Router();

const {
  register,
  verifyOTP,
  login,
  sendOTP,
  resetPassword
} = require('../controllers/authcontroller'); // ✅ Folder name is "controller"

router.post('/register', register);
router.post('/verify-otp', verifyOTP);
router.post('/login', login);
router.post('/send-otp', sendOTP);
router.post('/reset-password', resetPassword);

module.exports = router; // ✅ ESSENTIAL: export correctly
