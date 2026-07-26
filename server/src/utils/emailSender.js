const nodemailer = require('nodemailer');

const sendEmail = async (to, subject, html) => {
  const transporter = nodemailer.createTransport({
    service: 'gmail',
    auth: {
      user: process.env.EMAIL_USER,
      pass: process.env.EMAIL_PASS,
    },
  });

  const mailOptions = {
    from: `"Aaroh AI" <${process.env.EMAIL_USER}>`,
    to ,
    subject  ,
    html ,
  };

  try {
    const info = await transporter.sendMail(mailOptions);
    console.log("📨 OTP email sent:", info.response);
  } catch (err) {
    console.error("❌ Failed to send email:", err);
    throw err;
  }
};

module.exports = sendEmail;
