// controllers/authController.js
const User = require('../models/User');
const bcrypt = require('bcryptjs');
const jwt = require('jsonwebtoken');
const sendEmail = require('../utils/emailSender');
const generateToken = require('../utils/tokenGenerator');

// ✅ REGISTER
exports.register = async (req, res) => {
  console.log("🛠 Inside Register Controller");
  console.log("📦 Controller Body:", req.body);  // ✅ Yeh line daalo
  try {
    const {  email, password } = req.body;

    // Validate inputs
    if (  !email || !password) {
      return res.status(400).json({ error: 'All fields are required' });
    }

    // Check if user exists
    const existingUser = await User.findOne({ email });
    if (existingUser) {
      return res.status(400).json({ error: 'User already exists' });
    }

    // Hash password
    const hashedPassword = await bcrypt.hash(password, 10);

        // Generate OTP
const otp = Math.floor(100000 + Math.random() * 900000).toString();

    // Save new user
    const newUser = new User({
      
      email,
      password: hashedPassword,
      otp,
      otpExpires: Date.now() + 10 * 60 * 1000, // 10 minutes
      verified: false,
    });

    await newUser.save();
     // Send OTP Email
    await sendEmail(
      email,
      'Verify Your Email - project',
      `
      <div style="font-family: sans-serif; padding: 20px; background: #f0f4ff; border-radius: 8px;">
        <h2 style="color: #4B0082;">project working</h2>
        <p>Thanks for registering! Please verify your email using the OTP below:</p>
        <div style="font-size: 24px; font-weight: bold; background: #007bff; color: white; padding: 10px; border-radius: 5px; text-align: center;">${otp}</div>
        <p style="margin-top: 20px;">This OTP will expire in 10 minutes.</p>
      </div>
      `
    );

    res.status(201).json({ message: 'User registered. OTP sent to email.' });

  } catch (err) {
    console.error('❌ Registration error:', err);
    res.status(500).json({ error: 'Server error during registration' });
  }
};
  


// ✅ VERIFY OTP
exports.verifyOTP = async (req, res) => {
  const { email ,otp } = req.body;
  try {
    const user = await User.findOne({ email });
    if (!user) return res.status(404).json({ message: 'User not found' });

    if (user.otp !== otp || user.otpExpires < Date.now()) {
      return res.status(400).json({ message: 'Invalid or expired OTP' });
    }

    user.verified = true;
    user.otp = null;
    user.otpExpires = null;
    await user.save();

    res.status(200).json({ message: 'Email verified successfully' });
  } catch (err) {
    res.status(500).json({ message: 'OTP verification failed', error: err.message });
  }
};

// ✅ LOGIN

// controllers/authController.js

/*exports.login = async (req, res) => {
  const { email, password } = req.body;

  console.log("📩 Incoming OTP verification for:", email, otp);

  try {
    const user = await User.findOne({ email });
    if (!user) return res.status(404).json({ message: 'User not found' });

      console.log("👤 User found:", user.email);
    console.log("✅ Stored OTP:", user.otp);
    console.log("🕒 Expires At:", user.otpExpires);

    const isMatch = await bcrypt.compare(password, user.password);
    if (!isMatch) return res.status(401).json({ message: 'Invalid credentials' });

    // If not verified
    if (!user.verified) {
      const otp = Math.floor(100000 + Math.random() * 900000).toString();
      user.otp = otp;
      user.otpExpires = Date.now() + 10 * 60 * 1000;
      await user.save();

      await sendEmail(email, 'Verify Your Email - Aaroh AI', `
        <div style="font-family: sans-serif; background: #f0f4ff; padding: 20px;">
          <h2>OTP for Aaroh AI</h2>
          <p>Your OTP is:</p>
          <div style="font-size: 24px; background: #007bff; color: white; padding: 10px;">${otp}</div>
        </div>
      `);

      return res.status(403).json({ message: 'Please verify your email first', verify: true });
    }

    const token = generateToken(user._id);
    res.status(200).json({ message: 'Login successful', user: { email: user.email }, token });

  } catch (err) {
    res.status(500).json({ message: 'Login failed', error: err.message });
  }
};*/

exports.login = async (req, res) => {
  const { email, password } = req.body;
  try {
    const user = await User.findOne({ email });
    if (!user) return res.status(404).json({ message: 'User not found' });
    if (!user.verified) return res.status(403).json({ message: 'Please verify your email first' });

    const isMatch = await bcrypt.compare(password, user.password);
    if (!isMatch) return res.status(401).json({ message: 'Invalid credentials' });

    const token = generateToken(user._id);
    res.status(200).json({ message: 'Login successful', user: { email: user.email, name: user.name }, token });
  } catch (err) {
    res.status(500).json({ message: 'Login failed', error: err.message });
  }
};

// ✅ SEND OTP for Login/Forgot Password
/*exports.sendOTP = async (req, res) => {


  const { email } = req.body;
  try {
    const user = await User.findOne({ email });
    if (!user) return res.status(404).json({ message: 'User not found' });

    const otp = Math.floor(100000 + Math.random() * 900000).toString();
    user.otp = otp;
    user.otpExpires = Date.now() + 10 * 60 * 1000; // 10 mins
    await user.save();

    await sendEmail(email, 'Your OTP - Aaroh AI', `Your OTP is: ${otp}`);

    res.status(200).json({ message: 'OTP sent to email' });
  } catch (err) {
    res.status(500).json({ message: 'Failed to send OTP', error: err.message });
  }
};*/

// ✅ SEND OTP for Login/Forgot Password
exports.sendOTP = async (req, res) => {
  const { email } = req.body;
  try {
    const user = await User.findOne({ email });
    if (!user) return res.status(404).json({ message: 'User not found' });

    const otp = Math.floor(100000 + Math.random() * 900000).toString();
    user.otp = otp;
    user.otpExpires = Date.now() + 10 * 60 * 1000; // 10 minutes
    await user.save();

    const htmlContent = `
      <div style="font-family: Arial, sans-serif; max-width: 500px; margin: auto; padding: 20px; border: 1px solid #e5e5e5; border-radius: 10px; background-color: #f9f9f9;">
        <h2 style="color: #4b0082;">🎵 Welcome to Aaroh AI</h2>
        <p style="font-size: 16px; color: #333;">You’ve successfully registered on <strong>Aaroh AI</strong> – the ultimate platform for real-time music practice feedback.</p>
        
        <p style="font-size: 16px; color: #333;">Here is your OTP to verify your account:</p>
     
        

        <div style="margin: 20px 0; background-color: #007bff; color: #fff; font-size: 24px; font-weight: bold; padding: 15px; text-align: center; border-radius: 8px;">
          ${otp}
        </div>

        <p style="font-size: 16px; color: #333;">
          ✅ Track your pitch, tempo & tone <br>
          ✅ Get instant feedback <br>
          ✅ Visualize your progress with accuracy
        </p>

        <p style="font-size: 16px; color: #333;">We’re excited to have you on this musical journey. Start improving today! 🎶</p>

        <a href="https://aarohai.in/dashboard" style="display: inline-block; margin-top: 20px; padding: 10px 20px; background-color: #4b0082; color: #fff; text-decoration: none; border-radius: 5px;">🎧 Go to Dashboard</a>

        <hr style="margin-top: 30px;">
        <p style="font-size: 12px; color: #888; text-align: center;">This OTP is valid for 10 minutes. Do not share it with anyone.</p>
      </div>
    `;

    await sendEmail(email, `${otp}` , htmlContent);

    res.status(200).json({ message: 'OTP sent to email' });
  } catch (err) {
    console.error('❌ Failed to send OTP:', err);
    res.status(500).json({ message: 'Failed to send OTP', error: err.message });
  }
};



// ✅ RESET PASSWORD using OTP
exports.resetPassword = async (req, res) => {
  const { email, otp, newPassword } = req.body;
  try {
    const user = await User.findOne({ email });
    if (!user) return res.status(404).json({ message: 'User not found' });

    if (user.otp !== otp || user.otpExpires < Date.now()) {
      return res.status(400).json({ message: 'Invalid or expired OTP' });
    }

    const hashed = await bcrypt.hash(newPassword, 10);
    user.password = hashed;
    user.otp = null;
    user.otpExpires = null;
    await user.save();

    res.status(200).json({ message: 'Password reset successful' });
  } catch (err) {
    res.status(500).json({ message: 'Failed to reset password', error: err.message });
  }
};
