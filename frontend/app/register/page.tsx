export default function RegisterPage() {
  return (
    <section className="card card--subtle auth-card stack-sm" style={{ textAlign: 'center' }}>
      <h1 style={{ margin: 0, fontSize: '2rem', fontWeight: 600 }}>Регистрация</h1>
      <p style={{ margin: 0, color: 'var(--text-muted)', fontSize: '0.95rem' }}>
        На время тестирования регистрации хватает на странице входа. Перейдите на{' '}
        <a href="/login">/login</a>, введите новый логин и пароль — аккаунт создастся автоматически.
      </p>
    </section>
  );
}
