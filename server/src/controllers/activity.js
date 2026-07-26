exports.getRecentActivity = (req, res) => {
  res.json([
    { title: "Product Launch Video", date: "July 25, 2025", trendScore: 82 },
    { title: "Behind the Scenes", date: "July 24, 2025", trendScore: 75 }
  ]);
};
