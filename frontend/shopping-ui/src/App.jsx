import { useEffect, useState } from 'react';
import { Camera, ShoppingCart, Shield, ArrowRight, Package, Trash2 } from 'lucide-react';
import './App.css';

const API = 'http://127.0.0.1:8000';
const money = n => `Rs. ${Number(n || 0).toLocaleString('en-LK', {minimumFractionDigits:2, maximumFractionDigits:2})}`;

export default function App() {
  const [page, setPage] = useState('welcome');
  const [cart, setCart] = useState({items:[], count:0, total:0});
  const [health, setHealth] = useState(null);
  const [message, setMessage] = useState('');

  useEffect(() => {
    if (page !== 'shopping') return;
    let active = true;
    const refresh = async () => {
      try {
        const [c,h] = await Promise.all([
          fetch(`${API}/api/cart`).then(r=>r.json()),
          fetch(`${API}/api/health`).then(r=>r.json())
        ]);
        if (active) { setCart(c); setHealth(h); setMessage(''); }
      } catch { if (active) setMessage('Backend not reachable. Start FastAPI on port 8000.'); }
    };
    refresh();
    const interval = setInterval(refresh, 500);
    return () => { active = false; clearInterval(interval); };
  }, [page]);

  async function remove(id) {
    try {
      const r = await fetch(`${API}/api/cart/${id}`, {method:'DELETE'});
      const data = await r.json();
      if (!r.ok) throw new Error(data.detail || 'Unable to remove');
      setCart(data.cart);
    } catch(e) { setMessage(e.message); }
  }

  const Header = () => <header className="topbar">
    <button className="admin-link" onClick={()=>setPage('admin')}><Shield size={16}/> Admin Login</button>
    <div className="brand"><ShoppingCart size={24}/> Smart<span>Cart</span></div>
  </header>;

  if (page === 'welcome') return <div className="app"><Header/><main className="hero">
    <div className="eyebrow">THE FUTURE OF GROCERY SHOPPING</div>
    <h1>Shop smarter.<br/><span>Checkout faster.</span></h1>
    <p>Automatic product recognition, instant cart updates and live prices.</p>
    <button className="primary" onClick={()=>setPage('account')}>Start Shopping <ArrowRight size={18}/></button>
  </main></div>;

  if (page === 'account') return <div className="app"><Header/><main className="center">
    <section className="card account"><h2>Welcome to SmartCart</h2><p>Choose how to continue.</p>
    <button className="primary" onClick={()=>setMessage('Sign In is coming soon')}>Sign In</button>
    <button className="secondary" onClick={()=>setMessage('Sign Up is coming soon')}>Sign Up</button>
    <button className="secondary" onClick={()=>{setPage('shopping');setMessage('')}}>Continue Without Signing In</button>
    {message && <p>{message}</p>}</section>
  </main></div>;

  if (page === 'admin') return <div className="app"><Header/><main className="center"><section className="card account">
    <h2>Admin Login</h2><p>Authentication will be implemented later.</p>
    <button className="secondary" onClick={()=>setPage('welcome')}>Back to Welcome</button>
  </section></main></div>;

  return <div className="app"><Header/><main className="dashboard">
    <div className="heading"><div><div className="eyebrow">SMART SHOPPING SESSION</div><h1>Your Shopping Dashboard</h1><p>Products are recognized automatically after 2.5 seconds at 70% confidence.</p></div><span className="pill">{health?.camera || 'Connecting...'}</span></div>
    <div className="columns">
      <section className="card"><h2><Camera size={22}/> Live YOLO11 Camera</h2>
        <div className="video"><img src={`${API}/api/video`} alt="Live webcam with YOLO11 detection" /></div>
        <p className="hint">No manual detection. Hold each product steadily in view. Multiple different products can be detected together.</p>
        {message && <p className="notice">{message}</p>}
      </section>
      <section className="card cart"><div className="cart-head"><h2><ShoppingCart size={22}/> Your Cart</h2><span className="pill">{cart.count} items</span></div>
        <div className="items">{cart.items.length===0 ? <div className="empty"><Package size={40}/><h3>Your cart is empty</h3><p>Detected products will appear automatically.</p></div> : cart.items.map(item=><div className="item" key={item.id}>
          <Package size={24}/><div className="item-info"><strong>{item.name}</strong><span>{money(item.price)}</span><small>Inside basket — provisional (sensors not connected)</small></div>
          <button className="delete" disabled={item.in_basket} onClick={()=>remove(item.id)} title={item.in_basket?'Cannot delete until sensor-verified removal':'Delete item'}><Trash2 size={16}/></button>
        </div>)}</div>
        <div className="footer"><div className="total"><span>Total Price</span><strong>{money(cart.total)}</strong></div><button className="primary" onClick={()=>setMessage('Continue showing products to the webcam.')}>Continue Shopping</button></div>
      </section>
    </div>
  </main></div>;
}
