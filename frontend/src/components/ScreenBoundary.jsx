import { Component } from 'react'
export default class ScreenBoundary extends Component {
  state = { failed: false }
  static getDerivedStateFromError() { return { failed: true } }
  render() {
    const {t} = this.props
    return this.state.failed ? <section className="panel-page" role="alert"><h1>500</h1><h2>{t.serverFailureTitle}</h2><p>{t.serverError}</p><button className="btn-neon" onClick={()=>window.location.reload()}>{t.retry}</button></section> : this.props.children
  }
}
