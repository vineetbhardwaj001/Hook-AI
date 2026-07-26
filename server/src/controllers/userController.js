const User = require("../models/User");

// Get user profile
const getProfile = async (req, res) => {
  try {
    const user = await User.findById(req.user.id).select("firstName lastName email");
    if (!user) return res.status(404).json({ message: "User not found" });

    // Combine firstName + lastName
    const userData = {
      name: `${user.firstName} ${user.lastName}`.trim(),
      email: user.email,
    };

    res.json({ user: userData });
  } catch (err) {
    console.error(err);
    res.status(500).json({ message: "Server error" });
  }
};


// Delete user profile
const deleteProfile = async (req, res) => {
  try {
    await User.findByIdAndDelete(req.user.id);
    res.json({ message: "Profile deleted successfully" });
  } catch (err) {
    console.error(err);
    res.status(500).json({ message: "Server error" });
  }
};

module.exports = { getProfile, deleteProfile }; // ✅ correct export
