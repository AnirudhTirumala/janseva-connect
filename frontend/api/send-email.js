import nodemailer from "nodemailer";

export default async function handler(req, res) {
  // Allow only POST requests
  if (req.method !== "POST") {
    return res.status(405).json({ error: "Method not allowed" });
  }

  // Protect this endpoint so only the JanSeva backend can use it
  const authHeader = req.headers.authorization || "";
  const expectedSecret = process.env.EMAIL_API_SECRET || "";

  if (!expectedSecret || authHeader !== `Bearer ${expectedSecret}`) {
    return res.status(401).json({ error: "Unauthorized" });
  }

  try {
    const { to, subject, body } = req.body || {};

    if (!to || !subject || !body) {
      return res.status(400).json({
        error: "Missing required email fields",
      });
    }

    const transporter = nodemailer.createTransport({
      host: process.env.EMAIL_HOST || "smtp.gmail.com",
      port: Number(process.env.EMAIL_PORT || 587),
      secure: false,
      auth: {
        user: process.env.EMAIL_USER,
        pass: process.env.EMAIL_PASS,
      },
    });

    await transporter.sendMail({
      from:
        process.env.EMAIL_FROM ||
        `JanSeva Connect <${process.env.EMAIL_USER}>`,
      to,
      subject,
      text: body,
    });

    return res.status(200).json({
      success: true,
      message: "Email sent successfully",
    });
  } catch (error) {
    console.error("Email sending failed:", error);

    return res.status(500).json({
      error: "Could not send email",
    });
  }
}