function Toast({ message, visible }) {
  return (
    <div id="toast" className={visible ? 'toast' : 'toast hidden'}>
      {message}
    </div>
  );
}

export default Toast;