
import { useEffect, useRef, useState } from "react";
import "./App.css";

const API = "http://127.0.0.1:8000";

export default function App() {
  const videoRef = useRef(null);
  const busyRef = useRef(false);

  const [cameraEnabled, setCameraEnabled] = useState(false);
  const [cameraOn, setCameraOn] = useState(false);
  const [cameraError, setCameraError] = useState("");
  const [apiStatus, setApiStatus] = useState("Checking connection...");
  const [modelName, setModelName] = useState("Loading model...");
  const [classes, setClasses] = useState({});
  const [detections, setDetections] = useState([]);
  const [recent, setRecent] = useState([]);
  const [videoRatio, setVideoRatio] = useState(4 / 3);
  const [lastScan, setLastScan] = useState("--");

  // Check the Python backend and active model.
  useEffect(() => {
    fetch(`${API}/`)
      .then((response) => {
        if (!response.ok) throw new Error("Backend unavailable");
        return response.json();
      })
      .then((data) => {
        setApiStatus("Connected");
        setModelName(data.model || "YOLO model");
        setClasses(data.classes || {});
      })
      .catch(() => {
        setApiStatus("Backend offline");
        setModelName("Not connected");
      });
  }, []);

  // Start and stop the webcam and send frames to YOLO.
  useEffect(() => {
    if (!cameraEnabled) return;

    let stream;
    let cancelled = false;
    let timer;

    async function startCamera() {
      try {
        if (!navigator.mediaDevices?.getUserMedia) {
          throw new Error(
            "Camera access is unavailable in this browser."
          );
        }

        stream = await navigator.mediaDevices.getUserMedia({
          video: true,
          audio: false,
        });

        if (cancelled) {
          stream.getTracks().forEach((track) => track.stop());
          return;
        }

        const video = videoRef.current;
        if (!video) {
          stream.getTracks().forEach((track) => track.stop());
          return;
        }

        video.srcObject = stream;
        await video.play();

        if (cancelled) return;

        setCameraOn(true);
        setCameraError("");

        const canvas = document.createElement("canvas");
        const context = canvas.getContext("2d");

        // Send one frame per second to the Python API.
        timer = window.setInterval(async () => {
          if (
            busyRef.current ||
            !videoRef.current ||
            videoRef.current.readyState < 2
          ) {
            return;
          }

          busyRef.current = true;

          try {
            const currentVideo = videoRef.current;

            canvas.width = currentVideo.videoWidth;
            canvas.height = currentVideo.videoHeight;

            context.drawImage(currentVideo, 0, 0);

            const blob = await new Promise((resolve) =>
              canvas.toBlob(resolve, "image/jpeg", 0.75)
            );

            if (!blob || cancelled) return;

            const form = new FormData();
            form.append("file", blob, "webcam.jpg");

            const response = await fetch(`${API}/predict`, {
              method: "POST",
              body: form,
            });

            if (!response.ok) {
              throw new Error("Prediction request failed");
            }

            const result = await response.json();

            if (cancelled) return;

            const found = result.detections || [];

            // Keep detections in the results panel only.
            // No bounding boxes or labels are drawn over the video.
            setDetections(found);
            setLastScan(new Date().toLocaleTimeString());

            if (result.model) {
              setModelName(result.model);
            }

            // Record detected objects in the session activity.
            if (found.length > 0) {
              const timestamp = new Date().toLocaleTimeString();

              setRecent((previous) => [
                ...found.map((item) => ({
                  ...item,
                  time: timestamp,
                  id: `${Date.now()}-${Math.random()}`,
                })),
                ...previous,
              ].slice(0, 12));
            }

            setApiStatus("Connected");
          } catch (error) {
            if (!cancelled) {
              console.error("Detection error:", error);
              setApiStatus("Prediction error");
            }
          } finally {
            busyRef.current = false;
          }
        }, 1000);
      } catch (error) {
        if (!cancelled) {
          setCameraOn(false);
          setCameraError(
            error.message ||
              "Unable to access the camera. Check browser permissions."
          );
          setCameraEnabled(false);
        }
      }
    }

    startCamera();

    return () => {
      cancelled = true;
      window.clearInterval(timer);

      if (stream) {
        stream.getTracks().forEach((track) => track.stop());
      }

      setCameraOn(false);
    };
  }, [cameraEnabled]);

  const uniqueLabels = [
    ...new Set(detections.map((item) => item.label)),
  ];

  const classCount = Array.isArray(classes)
    ? classes.length
    : Object.keys(classes).length;

  function confidencePercent(value) {
    return `${Math.round(Number(value || 0) * 100)}%`;
  }

  function clearActivity() {
    setRecent([]);
  }

  function toggleCamera() {
    if (cameraEnabled) {
      setCameraEnabled(false);
      setDetections([]);
      setCameraOn(false);
      setCameraError("");
    } else {
      setCameraError("");
      setCameraEnabled(true);
    }
  }

  return (
    <div className="vision-app">
      {/* Header */}
      <header className="vision-header">
        <div className="vision-brand">
          <div className="vision-logo">S</div>

          <div>
            <h1>SmartTrolley</h1>
            <p>AI Vision &amp; Object Detection</p>
          </div>
        </div>

        <div className="header-right">
          <span
            className={`status-dot ${
              apiStatus === "Connected" ? "online" : ""
            }`}
          />
          <span>{apiStatus}</span>
        </div>
      </header>

      <main className="vision-main">
        {/* Hero */}
        <section className="vision-hero">
          <div>
            <span className="vision-eyebrow">
              COMPUTER VISION MODULE
            </span>

            <h2>Object Detection Studio</h2>

            <p>
              Identify objects in real time using your trained YOLO
              model and webcam.
            </p>
          </div>

          <div className="hero-model">
            <span className="model-icon">✳</span>

            <div>
              <small>ACTIVE MODEL</small>
              <strong>{modelName}</strong>
              <span>YOLO Object Detection</span>
            </div>
          </div>
        </section>

        {/* Summary cards */}
        <section className="metric-grid">
          <article className="metric-card">
            <div className="metric-icon">◉</div>
            <div>
              <span>Camera status</span>
              <strong>{cameraOn ? "Active" : "Inactive"}</strong>
            </div>
          </article>

          <article className="metric-card">
            <div className="metric-icon">⌗</div>
            <div>
              <span>Current detections</span>
              <strong>{detections.length}</strong>
            </div>
          </article>

          <article className="metric-card">
            <div className="metric-icon">◇</div>
            <div>
              <span>Unique objects</span>
              <strong>{uniqueLabels.length}</strong>
            </div>
          </article>

          <article className="metric-card">
            <div className="metric-icon">▤</div>
            <div>
              <span>Model classes</span>
              <strong>{classCount || "--"}</strong>
            </div>
          </article>
        </section>

        {cameraError && (
          <div className="vision-error">{cameraError}</div>
        )}

        {/* Detection workspace */}
        <section className="workspace-heading">
          <div>
            <span className="vision-eyebrow dark">
              LIVE MONITORING
            </span>

            <h2>Detection workspace</h2>

            <p>
              View your camera and inspect recognised objects.
            </p>
          </div>

          <span
            className={`camera-badge ${cameraOn ? "active" : ""}`}
          >
            <span
              className={`status-dot ${cameraOn ? "online" : ""}`}
            />
            {cameraOn ? "Live scanning" : "Camera stopped"}
          </span>
        </section>

        <section className="vision-workspace">
          {/* Camera panel */}
          <article className="camera-card">
            <div className="panel-heading">
              <div>
                <h3>Live camera feed</h3>
                <p>Real-time object recognition</p>
              </div>

              <span className="live-tag">
                {cameraOn ? "LIVE" : "STANDBY"}
              </span>
            </div>

            <div
              className="vision-camera-stage"
              style={{ aspectRatio: videoRatio }}
            >
              <video
                ref={videoRef}
                autoPlay
                muted
                playsInline
                onLoadedMetadata={(event) => {
                  const video = event.currentTarget;

                  if (video.videoWidth && video.videoHeight) {
                    setVideoRatio(
                      video.videoWidth / video.videoHeight
                    );
                  }
                }}
              />

              {/* No detection boxes or labels are drawn on the video. */}
              {!cameraOn && (
                <div className="camera-overlay">
                  <div className="camera-placeholder-icon">◎</div>

                  <strong>Camera preview</strong>

                  <span>
                    Start the camera to begin object detection.
                  </span>
                </div>
              )}
            </div>

            <div className="camera-toolbar">
              <div className="camera-description">
                <span
                  className={`status-dot ${
                    cameraOn ? "online" : ""
                  }`}
                />

                <span>
                  {cameraOn
                    ? "Camera is processing frames"
                    : "Camera is ready"}
                </span>
              </div>

              <button
                className={
                  cameraEnabled ? "stop-button" : "start-button"
                }
                onClick={toggleCamera}
              >
                {cameraEnabled
                  ? "■ Stop camera"
                  : "▶ Start detection"}
              </button>
            </div>
          </article>

          {/* Detection results and model details */}
          <aside className="results-column">
            <article className="results-card">
              <div className="panel-heading">
                <div>
                  <h3>Detection results</h3>
                  <p>Objects in the current frame</p>
                </div>

                <span className="result-count">
                  {detections.length}
                </span>
              </div>

              {detections.length === 0 ? (
                <div className="empty-results">
                  <div className="empty-icon">⌕</div>

                  <strong>No objects detected</strong>

                  <p>
                    Start scanning and place an object from your
                    model's trained classes in front of the camera.
                  </p>
                </div>
              ) : (
                <div className="result-list">
                  {detections.map((item, index) => (
                    <div
                      className="result-item"
                      key={`${item.class_id}-${index}`}
                    >
                      <div className="object-symbol">◇</div>

                      <div className="result-details">
                        <strong>{item.label}</strong>

                        <div className="confidence-track">
                          <div
                            className="confidence-fill"
                            style={{
                              width: confidencePercent(
                                item.confidence
                              ),
                            }}
                          />
                        </div>

                        <small>
                          Confidence:{" "}
                          {confidencePercent(item.confidence)}
                        </small>
                        <div className="remove-item-message" role="alert">
                          ⚠ Please remove the item
                        </div>
                      </div>

                      <span className="detected-check">✓</span>
                    </div>
                  ))}
                </div>
              )}

              <div className="last-scan">
                <span>Last scan</span>
                <strong>{lastScan}</strong>
              </div>
            </article>

            <article className="model-card">
              <div className="model-card-heading">
                <span className="model-small-icon">✳</span>

                <div>
                  <h3>Model information</h3>
                  <p>Inference service</p>
                </div>
              </div>

              <div className="model-detail">
                <span>Model file</span>
                <strong>{modelName}</strong>
              </div>

              <div className="model-detail">
                <span>Backend</span>

                <strong
                  className={
                    apiStatus === "Connected" ? "green-text" : ""
                  }
                >
                  {apiStatus}
                </strong>
              </div>

              <div className="model-detail">
                <span>Classes available</span>
                <strong>{classCount || "Not loaded"}</strong>
              </div>
            </article>
          </aside>
        </section>

        {/* Recent activity */}
        <section className="activity-card">
          <div className="activity-heading">
            <div>
              <span className="vision-eyebrow dark">
                SESSION ACTIVITY
              </span>

              <h2>Recent detections</h2>

              <p>
                Objects recognised during this camera session.
              </p>
            </div>

            <button
              className="clear-button"
              onClick={clearActivity}
              disabled={recent.length === 0}
            >
              Clear activity
            </button>
          </div>

          {recent.length === 0 ? (
            <div className="activity-empty">
              Recent detections will appear here when the model
              recognises objects.
            </div>
          ) : (
            <div className="activity-table-wrap">
              <table className="activity-table">
                <thead>
                  <tr>
                    <th>Object</th>
                    <th>Confidence</th>
                    <th>Time</th>
                    <th>Status</th>
                  </tr>
                </thead>

                <tbody>
                  {recent.map((item) => (
                    <tr key={item.id}>
                      <td>
                        <span className="table-object-icon">◇</span>
                        {item.label}
                      </td>

                      <td>{confidencePercent(item.confidence)}</td>
                      <td>{item.time}</td>

                      <td>
                        <span className="table-status">
                          Detected
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        <footer className="vision-footer">
          <span>SmartTrolley · AI Vision Module</span>
          <span>Powered by YOLO and FastAPI</span>
        </footer>
      </main>
    </div>
  );
}
