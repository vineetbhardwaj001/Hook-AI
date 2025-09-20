const express = require("express");
const router = express.Router();
const authMiddleware = require("../controllers/authMiddleware");
const { getProfile, deleteProfile } = require("../controllers/userController"); // ✅ must match export

router.get("/", authMiddleware, getProfile);
router.delete("/", authMiddleware, deleteProfile);

module.exports = router;
